import aiohttp
import argparse
import asyncio
import async_timeout
import contextlib
import csv
import datetime
import os
from collections.abc import AsyncIterator
from pathlib import Path
from contact_energy_nz import ContactEnergyApi, UsageDatum

OUTPUT_HEADERS = ['hour', 'kwh', 'price', 'uncharged_kwh', 'offpeak_kwh', 'offpeak_price']
TIMEOUT: float = 15 # seconds
GENESIS_USAGE_URL = "https://web-api.genesisenergy.co.nz/v2/private/electricity/site-usage"

class UsageDownloader:
	"""
	Base class for provider-specific hourly energy usage downloaders.

	Responsibilities:
		- Owns the date-range download loop and per-day error handling
		- Manages the transport session lifecycle shared across the run
		- Writes data to CSV files in the output directory using the standard shape
		- Prevents duplicate downloads unless overwrite=True

	Subclasses provide provider-specific authentication and fetch a single day's
	usage by implementing download_async.
	"""

	def __init__(self, output_dir: str):
		self.output_dir = output_dir

	async def download(self, date_start: datetime.date, date_end: datetime.date, overwrite: bool = False):
		if date_start > date_end:
			print(f"Start date {str(date_start)} is greater than end date {str(date_end)}")
			return

		async with self._download_session() as session:
			# Loop through dates in reverse order (end to start)
			date = date_end
			while date >= date_start:
				print(f"Downloading data for {str(date)}...")
				try:
					data = await self.download_async(session, date)
					if data is None:
						continue
					self.write(date, data, overwrite)
				except Exception as error:
					print(f"Failed to download {str(date)}: {error}")
				date = date - datetime.timedelta(days=1)

	@contextlib.asynccontextmanager
	async def _download_session(self) -> AsyncIterator[aiohttp.ClientSession | None]:
		"""Providers that need a persistent transport session yield it here."""
		yield None

	async def download_async(self, session: aiohttp.ClientSession | None, date: datetime.date) -> list[UsageDatum] | None:
		raise NotImplementedError

	def write(self, date: datetime.date, data: list[UsageDatum], overwrite: bool = False) -> bool:
		path = Path(self.output_dir, date.strftime("%Y%m%d") + ".csv")
		if not overwrite and path.is_file():
			print(f"Not overwriting {str(path)}")
			return False

		with open(str(path), 'w', newline='') as output_file:
			csv_writer = csv.writer(output_file)
			csv_writer.writerow(OUTPUT_HEADERS)
			for d in data:
				csv_writer.writerow([d.date.hour, d.value, d.dollar_value, d.uncharged_value, d.offpeak_value, d.offpeak_dollar_value])
		print(f"Wrote data to: {str(path)}")
		return True

class ContactEnergyUsageDownloader(UsageDownloader):
	"""
	Downloads hourly energy usage data from the Contact Energy API and saves it to CSV files.

	Responsibilities:
		- Authenticates with Contact Energy API using either token or username/password
		- Downloads hourly usage data for a date range
		- Writes data to CSV files in the specified output directory
		- Prevents duplicate downloads unless overwrite=True
	"""

	def __init__(self, output_dir: str, account_id: str, contract_id: str, token: str, username: str, password: str):
		super().__init__(output_dir)
		self.account_id = account_id
		self.contract_id = contract_id
		self.token = token
		self.username = username
		self.password = password
		self.connector: ContactEnergyApi

	@contextlib.asynccontextmanager
	async def _download_session(self) -> AsyncIterator[aiohttp.ClientSession | None]:
		# Authenticate once per run, inside the async context so credential auth can be awaited
		if self.token is not None and self.token != "":
			print("Authenticating with token...")
			self.connector = ContactEnergyApi.from_token(self.token)
		else:
			print("Authenticating with username and password...")
			self.connector = await ContactEnergyApi.from_credentials(self.username, self.password)

		# Hack in the account and contract ID to avoid having to call account_summary() which populates these
		self.connector.account_id = self.account_id
		self.connector.contract_id = self.contract_id
		yield None

	async def download_async(self, session: aiohttp.ClientSession | None, date: datetime.date) -> list[UsageDatum]:
		async with async_timeout.timeout(TIMEOUT):
			data: list[UsageDatum] = await self.connector.get_hourly_usage(date)  # type: ignore[arg-type]
			return data

class GenesisEnergyUsageDownloader(UsageDownloader):
	"""
	Downloads hourly energy usage data from the Genesis Energy API and saves it to CSV files.

	Responsibilities:
		- Authenticates with the Genesis Energy API using a bearer token
		- Downloads hourly usage data for a date range
		- Writes data to CSV files in the specified output directory using the same
		  shape as the Contact Energy downloader
		- Prevents duplicate downloads unless overwrite=True
	"""

	def __init__(self, output_dir: str, token: str):
		if token is None or token == "":
			raise ValueError("Genesis Energy token is empty")
		super().__init__(output_dir)
		self.token = token

	@contextlib.asynccontextmanager
	async def _download_session(self) -> AsyncIterator[aiohttp.ClientSession | None]:
		async with aiohttp.ClientSession() as session:
			yield session

	async def download_async(self, session: aiohttp.ClientSession | None, date: datetime.date) -> list[UsageDatum] | None:
		assert session is not None
		headers = {
			"accept": "application/json",
			"authorization": f"Bearer {self.token}",
			"brand-id": "GENE",
			"content-type": "application/json",
		}
		payload = {
			"startDate": date.strftime("%Y-%m-%d"),
			"endDate": date.strftime("%Y-%m-%d"),
			"intervalType": "HOURLY",
		}
		async with async_timeout.timeout(TIMEOUT):
			async with session.post(GENESIS_USAGE_URL, headers=headers, json=payload) as response:
				response.raise_for_status()
				body = await response.json()
		items = sorted(body.get("usage", []), key=lambda item: item["startDate"])
		data = [self._to_usage_datum(item) for item in items]
		if all(d.value == 0 for d in data):
			print(f"WARNING: Usage data for {str(date)} is not available yet, skipping")
			return None
		return data

	@staticmethod
	def _to_usage_datum(item: dict) -> UsageDatum:
		start = datetime.datetime.fromisoformat(item["startDate"])
		return UsageDatum({
			"currency": "NZD",
			"date": start.strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
			"value": item["kw"],
			"dollarValue": item["unroundedCost"],
			"offpeakValue": None,
			"unchargedValue": None,
			"offpeakDollarValue": None,
			"unit": "kWh",
		})

# Load .env file
with open(".env") as f:
	for line in f:
		if line.startswith("#") or line.strip() == "":
			continue # Skip comments and blanks
		key, value = line.strip().split("=", 1)
		os.environ[key] = value

def run_contact_energy(start: datetime.date, end: datetime.date):
	# Authenticates with Contact Energy only when this downloader is selected
	downloader = ContactEnergyUsageDownloader("data", os.getenv("ACCOUNT_ID", ""), os.getenv("CONTRACT_ID", ""), os.getenv("TOKEN", ""), os.getenv("USERNAME", ""), os.getenv("PASSWORD", ""))
	asyncio.run(downloader.download(start, end, False))

def run_genesis_energy(start: datetime.date, end: datetime.date):
	# Authenticates with Genesis Energy only when this downloader is selected
	downloader = GenesisEnergyUsageDownloader("data", os.getenv("GENESIS_TOKEN", ""))
	asyncio.run(downloader.download(start, end, False))

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Download hourly electricity usage data from a single provider.")
	parser.add_argument("provider", choices=["contact", "genesis"], help="Which provider's usage to download")
	parser.add_argument("--start", required=True, type=datetime.date.fromisoformat, help="Start date, inclusive (YYYY-MM-DD)")
	parser.add_argument("--end", required=True, type=datetime.date.fromisoformat, help="End date, inclusive (YYYY-MM-DD)")
	args = parser.parse_args()

	if args.provider == "contact":
		run_contact_energy(args.start, args.end)
	elif args.provider == "genesis":
		run_genesis_energy(args.start, args.end)
