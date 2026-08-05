import asyncio
import async_timeout
import csv
import datetime
import os
from pathlib import Path
from contact_energy_nz import ContactEnergyApi, UsageDatum

OUTPUT_HEADERS = ['hour', 'kwh', 'price', 'uncharged_kwh', 'offpeak_kwh', 'offpeak_price']
TIMEOUT: float = 15 # seconds

class ContactEnergyUsageDownloader:
	"""
	Downloads hourly energy usage data from the Contact Energy API and saves it to CSV files.

	Responsibilities:
		- Authenticates with Contact Energy API using either token or username/password
		- Downloads hourly usage data for a date range
		- Writes data to CSV files in the specified output directory
		- Prevents duplicate downloads unless overwrite=True
	"""

	def __init__(self, output_dir: str, account_id: str, contract_id: str, token: str, username: str, password: str):
		# Authenticate
		if token is not None and token != "":
			print("Authenticating with token...")
			self.connector: ContactEnergyApi = ContactEnergyApi.from_token(token)
		else:
			print("Authenticating with username and password...")
			self.connector: ContactEnergyApi = ContactEnergyApi.from_credentials(username, password)

		# Hack in the account and contract ID to avoid having to call account_summary() which populates these
		self.connector.account_id = account_id
		self.connector.contract_id = contract_id

		self.output_dir = output_dir

	async def download(self, date_start: datetime.date, date_end: datetime.date, overwrite: bool = False):
		if date_start > date_end:
			print(f"Start date {str(date_start)} is greater than end date {str(date_end)}")
			return

		# Loop through dates in reverse order (end to start)
		date = date_end
		while date >= date_start:
			print(f"Downloading data for {str(date)}...")
			data = await self.download_async(date)
			self.write(date, data, overwrite)
			date = date - datetime.timedelta(days=1)

	async def download_async(self, date: datetime.date) -> list[UsageDatum]:
		async with async_timeout.timeout(TIMEOUT):
			data: list[UsageDatum] = await self.connector.get_hourly_usage(date)
			return data

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

# Load .env file
with open(".env") as f:
	for line in f:
		if line.startswith("#") or line.strip() == "":
			continue # Skip comments and blanks
		key, value = line.strip().split("=", 1)
		os.environ[key] = value

downloader: ContactEnergyUsageDownloader = ContactEnergyUsageDownloader("data", os.getenv("ACCOUNT_ID", ""), os.getenv("CONTRACT_ID", ""), os.getenv("TOKEN", ""), os.getenv("USERNAME", ""), os.getenv("PASSWORD", ""))

if __name__ == "__main__":
	start = datetime.date(2025, 6, 1)
	end =   datetime.date(2026, 6, 30)
	asyncio.run(downloader.download(start, end, False))
