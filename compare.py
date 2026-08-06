import csv
import os
from datetime import datetime, date
from typing import Dict, List

def _safe_float(row: dict, key: str, default: float = 0.0) -> float:
	"""Return row[key] as a float, or default if missing/empty."""
	val = row.get(key, default)
	if isinstance(val, str):
		val = val.strip()
		return float(val) if val else default
	return float(val) if val else default


MONTH_NAME_TO_MONTH = {
	"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
	"Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

def load_powershop_prices(csv_path: str) -> Dict[str, Dict[str, float]]:
	"""
	Load Powershop monthly prices from CSV file.
	Returns dictionary mapping month (e.g., "01" for January) to rates for each plan type.

	Structure:
	- standard_anytime: Flat rate (Anytime column)
	- standard_peak: Peak rate
	- standard_offpeak: Off-peak rate
	"""
	if not os.path.exists(csv_path):
		return {
			"standard_anytime": {},
			"standard_peak": {},
			"standard_offpeak": {},
		}

	prices = {
		"standard_anytime": {},
		"standard_peak": {},
		"standard_offpeak": {},
	}

	with open(csv_path, 'r') as f:
		reader = csv.DictReader(f)
		for row in reader:
			if row.get('Type') == 'Standard user, Standard Rates, Uncontrolled connections - Anytime':
				plan_prices = prices["standard_anytime"]
			elif row.get('Type') == 'Standard user, Standard Rates, Uncontrolled connections - Off Peak':
				plan_prices = prices["standard_offpeak"]
			elif row.get('Type') == 'Standard user, Standard Rates, Uncontrolled connections - Peak':
				plan_prices = prices["standard_peak"]
			else:
				print(f"Skipping unknown Powershop monthly plan {row.get('Type')}")
				continue

			# Get month from column name and convert to YYYY-MM format
			for month_col in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
				if month_col in row and row[month_col]:
					try:
						price = float(row[month_col])
						month_num = MONTH_NAME_TO_MONTH[month_col]
						plan_prices[month_num] = price
					except ValueError:
						continue

	return prices


class PlanComparison:
	"""
	Class for comparing energy plan costs and analysing usage patterns.

	This class provides tools to:
		1. Load hourly usage data from CSV files
		2. Calculate costs for different energy plans
		3. Identify free periods (off-peak hours)
		4. Compare plan savings across time periods
		5. Generate monthly and total cost reports

	Plans supported:
		- standard: Base rate with daily charge
		- good_weekends: Free 9am-5pm on weekends
		- good_nights: Free 9pm-midnight on weekdays
		- good_charge: Half-price 9pm-7am
		- powershop_anytime: Powershop flat rate (no daily charge)
		- powershop_shifty: Powershop peak/off-peak with shifty logic
	"""

	# Standard plan pricing configuration (ex GST) - daily charges per day
	PLANS = {
		"standard": {
			"rate": 0.244,         # $/kWh
			"levy": 0.0019,        # $/kWh
			"daily_charge": 2.801, # $/day
			"free_periods": [],    # (hour_start, hour_end, day_type)
		},
		"standard_low_user": {
			"rate": 0.288,       # $/kWh
			"levy": 0.0019,      # $/kWh
			"daily_charge": 1.8, # $/day
			"free_periods": [],  # (hour_start, hour_end, day_type)
		},
		"good_weekends": {
			"rate": 0.247,       # $/kWh
			"levy": 0,           # $/kWh
			"daily_charge": 3.1, # $/day
			"free_periods": [    # 9am to 5pm on weekends
				(9, 17, "weekend"),
			],
		},
		"good_weekends_low_user": {
			"rate": 0.316,       # $/kWh
			"levy": 0,           # $/kWh
			"daily_charge": 1.8, # $/day
			"free_periods": [    # 9am to 5pm on weekends
				(9, 17, "weekend"),
			],
		},
		"good_nights": {
			"rate": 0.293,          # $/kWh
			"levy": 0,              # $/kWh
			"daily_charge": 3.0001, # $/day
			"free_periods": [    # 9pm to midnight Monday to Friday
				(21, 24, "weekday"),
			],
		},
		"good_nights_low_user": {
			"rate": 0.359,       # $/kWh
			"levy": 0,           # $/kWh
			"daily_charge": 1.8, # $/day
			"free_periods": [    # 9pm to midnight Monday to Friday
				(21, 24, "weekday"),
			],
		},
		"good_charge": {
			"rate": 0.287,         # $/kWh
			"levy": 0,             # $/kWh
			"daily_charge": 3.101, # $/day
			"free_periods": [],  # No free periods, but has half-price periods
			"half_price_periods": [  # 9pm to 7am at half rate
				(21, 7),  # starts at hour 21, ends at hour 7 (next day)
			],
		},
		"good_charge_low_user": {
			"rate": 0.346,       # $/kWh
			"levy": 0,           # $/kWh
			"daily_charge": 1.8, # $/day
			"free_periods": [],  # No free periods, but has half-price periods
			"half_price_periods": [  # 9pm to 7am at half rate
				(21, 7),  # starts at hour 21, ends at hour 7 (next day)
			],
		},
		"genesis_standard": {
			"rate": 0.2481,         # $/kWh
			"levy": 0,              # $/kWh
			"daily_charge": 2.2848, # $/day
			"free_periods": []  # No free periods, but has half-price periods
		},
		"genesis_standard_low_user": {
			"rate": 0.2858,         # $/kWh
			"levy": 0,              # $/kWh
			"daily_charge": 1.4550, # $/day
			"free_periods": []  # No free periods, but has half-price periods
		},
		"genesis_time_varied": {
			"rate": 0,              # Will be loaded from CSV
			"levy": 0,              # $/kWh
			"daily_charge": 2.2848, # $/day
			"free_periods": [],     # No free periods, uses peak and off peak pricing
			"source": "genesis_auckland_prices.csv"
		},
		"genesis_time_varied_low_user": {
			"rate": 0.0,            # Will be loaded from CSV
			"levy": 0,              # $/kWh
			"daily_charge": 1.4550, # $/day
			"free_periods": [],     # No free periods, uses peak and off peak pricing
			"source": "genesis_low_user_auckland_prices.csv"
		},
		"powershop_anytime": {
			"rate": 0.0,  # Will be loaded from CSV. Does this include GST???
			"levy": 0.0,  # Will be loaded from CSV
			"daily_charge": 3.1303,  # Powershop daily charge
			"free_periods": [],
			"source": "powershop_auckland_vector_prices.csv",
		},
		"powershop_shifty": {
			"rate": 0.0,  # Will be loaded from CSV (peak rate). Does this include GST???
			"levy": 0.0,  # Will be loaded from CSV
			"daily_charge": 3.1303,  # Powershop daily charge
			"free_periods": [],
			"source": "powershop_auckland_vector_prices.csv",
		}
	}

	# Shifty peak hours: weekdays 7-11am and 6-9pm
	SHIFTY_PEAK_START = 7
	SHIFTY_PEAK_END = 11
	SHIFTY_EVENING_START = 18
	SHIFTY_EVENING_END = 21

	# Genesis time-varied peak hours: 7am to 9pm
	GENESIS_PEAK_START = 7
	GENESIS_PEAK_END = 21

	def __init__(self, data_dir: str, powershop_prices_path: str = "powershop_auckland_vector_prices.csv"):
		"""
		Load .csv files from the data_dir and Powershop prices.

		Args:
			data_dir: Directory containing CSV files with usage data. Files should be named
				in YYYYMMDD format (e.g., "20250601.csv").
			powershop_prices_path: Path to CSV file with Powershop monthly prices.
		"""

		self.data_dir = data_dir
		self.powershop_prices_path = powershop_prices_path
		self.data: Dict[date, List[Dict]] = {}
		self.powershop_monthly_prices: Dict[str, Dict[str, float]] = {}
		self.genesis_time_varied_prices: Dict[str, Dict[str, Dict[str, float]]] = {}

		# Load Powershop prices (once)
		self.powershop_monthly_prices = load_powershop_prices(powershop_prices_path)

		# Load Genesis time-varied prices for Auckland
		self.genesis_time_varied_prices["genesis_time_varied"] = load_genesis_time_varied_prices("genesis_auckland_prices.csv")
		self.genesis_time_varied_prices["genesis_time_varied_low_user"] = load_genesis_time_varied_prices("genesis_low_user_auckland_prices.csv")

		# Load all CSV files from the directory
		if os.path.exists(self.data_dir):
			for filename in os.listdir(self.data_dir):
				if filename.endswith('.csv'):
					filepath = os.path.join(self.data_dir, filename)
					date_from_filename = filename[:-4]  # Remove .csv extension

					with open(filepath, 'r') as f:
						reader = csv.DictReader(f)
						rows = []
						parsed_date = datetime.strptime(date_from_filename, "%Y%m%d").date()

						for row in reader:
							# Convert hour to integer for comparison
							row['hour'] = int(row['hour'])
							row['kwh'] = float(row['kwh'])
							# Handle empty price field (use 0 if empty)
							price_str = row['price'].strip()
							row['price'] = float(price_str) if price_str else 0.0
							# Handle optional fields that may be missing from CSV
							row['uncharged_kwh'] = _safe_float(row, 'uncharged_kwh')
							row['offpeak_kwh'] = _safe_float(row, 'offpeak_kwh')
							row['offpeak_price'] = _safe_float(row, 'offpeak_price')
							# Store the date in each row for later use
							row['date'] = parsed_date
							rows.append(row)

						if parsed_date not in self.data:
							self.data[parsed_date] = []
						self.data[parsed_date].extend(rows)

	def is_weekend(self, d: date) -> bool:
		"""Check if a date is a weekend"""
		return d.weekday() >= 5

	def is_weekday(self, d: date) -> bool:
		"""Check if a date is a weekday"""
		return d.weekday() < 5

	def _is_in_hour_range(self, hour: int, start: int, end: int) -> bool:
		"""Check if hour is in range [start, end). Note: hour 0-24"""
		if start < end:
			return start <= hour < end
		else:
			# Handles overnight ranges like 21 to 7
			return hour >= start or hour < end

	def is_free_period(self, hour: int, d: date, plan: str) -> bool:
		"""Check if the given hour falls within a free period for this plan"""
		if plan not in self.PLANS:
			return False

		_plan = self.PLANS[plan]
		for start_hour, end_hour, day_type in _plan.get("free_periods", []):
			if day_type == "weekend" and self.is_weekend(d):
				if self._is_in_hour_range(hour, start_hour, end_hour):
					return True
			elif day_type == "weekday" and self.is_weekday(d):
				if self._is_in_hour_range(hour, start_hour, end_hour):
					return True
		return False

	def is_shifted_hour(self, hour: int, d: date, plan: str) -> bool:
		"""
		Check if the given hour falls within a shifty period (off-peak pricing during peak hours).
		For powershop_shifty: weekdays 7-11am and 6-9pm use off-peak rate.
		"""
		if plan != "powershop_shifty":
			return False

		# Only on weekdays for shifty
		if not self.is_weekday(d):
			return False

		# Check if hour is in peak range: 7-11am or 6-9pm
		if self._is_in_hour_range(hour, self.SHIFTY_PEAK_START, self.SHIFTY_PEAK_END):
			return True
		if self._is_in_hour_range(hour, self.SHIFTY_EVENING_START, self.SHIFTY_EVENING_END):
			return True

		return False

	def is_half_price_period(self, hour: int, d: date, plan: str) -> bool:
		"""Check if the given hour falls within a half-price period for this plan"""
		if plan not in self.PLANS:
			return False

		_plan = self.PLANS[plan]
		for start_hour, end_hour in _plan.get("half_price_periods", []):
			if self._is_in_hour_range(hour, start_hour, end_hour):
				return True
		return False

	def _get_rate(self, row: Dict, plan: str) -> float:
		"""
		Get the appropriate rate for a given plan, accounting for:
		- Powershop monthly prices from CSV
		- Standard plan rates
		- Shifty peak/off-peak logic
		- Half price periods (good_charge)
		- Genesis time-varied peak/off-peak pricing
		"""
		_plan = self.PLANS[plan]
		hour = row['hour']
		month_key = row['date'].strftime("%m")

		# Standard plans use fixed rates
		if plan in ["standard", "good_weekends", "good_nights"]:
			return _plan["rate"]

		# good_charge / good_charge_low_user have half-price periods (9pm to 7am at half rate)
		if plan in ["good_charge", "good_charge_low_user"]:
			if self.is_half_price_period(hour, row['date'], plan):
				return _plan["rate"] / 2
			return _plan["rate"]

		# Genesis time-varied plans (peak GENESIS_PEAK_START to GENESIS_PEAK_END, off-peak remainder)
		if plan in ["genesis_time_varied", "genesis_time_varied_low_user"]:
			genesis_prices = self.genesis_time_varied_prices[plan]
			peak_price_key = genesis_prices["peak"]
			off_peak_price_key = genesis_prices["off_peak"]

			# Use GENESIS_PEAK_START and GENESIS_PEAK_END constants
			if self.GENESIS_PEAK_START <= hour < self.GENESIS_PEAK_END: # Peak hours
				if month_key in peak_price_key:
					return peak_price_key[month_key]
				else:
					raise RuntimeError(f"Couldn't find Genesis peak rate for month key {month_key}")
			else:  # Off-peak hours
				if month_key in off_peak_price_key:
					return off_peak_price_key[month_key]
				else:
					raise RuntimeError(f"Couldn't find Genesis off-peak rate for month key {month_key}")

		# Powershop plans
		if plan == "powershop_anytime":
			# Use anytime rate from CSV
			if month_key in self.powershop_monthly_prices["standard_anytime"]:
				return self.powershop_monthly_prices["standard_anytime"][month_key]
			raise RuntimeError(f"Couldn't find Powershop anytime rate for month key {month_key}")

		elif plan == "powershop_shifty":
			# Use peak rate from CSV, but off-peak rate during shifted hours
			if month_key in self.powershop_monthly_prices["standard_offpeak"]:
				if self.is_shifted_hour(hour, row['date'], plan):
					# Use off-peak rate during shifted hours
					return self.powershop_monthly_prices["standard_offpeak"][month_key]
				if month_key in self.powershop_monthly_prices["standard_peak"]:
					# Use peak rate during normal hours
					return self.powershop_monthly_prices["standard_peak"][month_key]
			raise RuntimeError(f"Couldn't find Powershop shifty rates for month key '{month_key}'")

		return _plan["rate"]

	def calculate_hourly_cost(self, row: Dict, plan: str) -> float:
		"""Calculate cost for a single hour of usage under a given plan"""
		kwh = row['kwh']
		hour = row['hour']

		base_rate = self._get_rate(row, plan)
		levy = self.PLANS[plan]["levy"]

		# Check if free period (completely free power)
		if self.is_free_period(hour, row['date'], plan):
			return 0.0

		# Cost for this hour: kwh times rate + levy
		hourly_cost = kwh * (base_rate + levy)
		return hourly_cost

	def calculate_daily_cost(self, rows: List[Dict], plan: str) -> float:
		"""Calculate total cost for all hours in a day under a given plan"""
		total_cost = 0.0

		for row in rows:
			hourly_cost = self.calculate_hourly_cost(row, plan)
			total_cost += hourly_cost

		# Add daily charge for this day (only once per day)
		total_cost += self.PLANS[plan]["daily_charge"]

		return total_cost

	def compare(self):
		"""Compare plans breaking down price per month and total usage
		Returns a list of dicts for CSV output with plans as columns

		Plans included:
		- standard, good_weekends, good_nights, good_charge (original plans)
		- powershop_anytime, powershop_shifty (new additions)
		"""
		if not self.data:
			return []

		# Group by month: structure is {month_name: {plan_name: cost}}
		monthly_costs: Dict[str, Dict[str, float]] = {}

		# Process each date
		for d in sorted(self.data.keys()):
			rows = self.data[d]

			# Calculate daily cost for each plan
			daily_costs = {}
			for plan_name in self.PLANS.keys():
				daily_costs[plan_name] = self.calculate_daily_cost(rows, plan_name)

			# Determine month (using first hour's date for consistency)
			if rows:
				month = rows[0]['date'].strftime("%Y-%m")
			else:
				month = d.strftime("%Y-%m")

			# Initialize month if not exists
			if month not in monthly_costs:
				monthly_costs[month] = {plan_name: 0.0 for plan_name in self.PLANS.keys()}

			# Accumulate monthly costs
			for plan_name, cost in daily_costs.items():
				monthly_costs[month][plan_name] += cost

		# Build output rows
		output_rows = []

		# Get sorted list of unique months
		sorted_months = sorted(monthly_costs.keys())

		for m in sorted_months:
			row: dict[str, str|float] = {'Month': m}
			for plan_name in self.PLANS.keys():
				# Show actual cost for each plan
				row[plan_name] = round(monthly_costs[m][plan_name], 2)

			output_rows.append(row)

		# Add total row
		total_row: dict[str, str|float] = {'Month': 'Total'}
		for plan_name in self.PLANS.keys():
			total_row[plan_name] = round(sum(monthly_costs[m][plan_name] for m in monthly_costs.keys()), 2)

		output_rows.append(total_row)

		return output_rows

def load_genesis_time_varied_prices(csv_path: str) -> Dict[str, Dict[str, float]]:
    """
    Load Genesis time-varied prices from CSV file.
    Returns dictionary mapping month (e.g., "01" for January) to peak and off-peak rates.

    CSV format:
        Type,Jan,Feb,Mar,...
        "Genesis time-varied - Peak",30.48,...
        "Genesis time-varied - Off Peak",20.64,...

    Returns structure:
        {
            "peak": {"01": 30.48, ...},
            "off_peak": {"01": 20.64, ...}
        }
    """
    if not os.path.exists(csv_path):
        return {
            "peak": {},
            "off_peak": {},
        }

    prices = {
        "peak": {},
        "off_peak": {},
    }

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Peak pricing
            if row.get('Type') == 'Genesis time-varied - Peak':
                for month_col in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                    if month_col in row and row[month_col]:
                        try:
                            price = float(row[month_col])
                            month_num = MONTH_NAME_TO_MONTH[month_col]
                            prices["peak"][month_num] = price
                        except ValueError:
                            continue
            # Off-peak pricing
            elif row.get('Type') == 'Genesis time-varied - Off Peak':
                for month_col in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                    if month_col in row and row[month_col]:
                        try:
                            price = float(row[month_col])
                            month_num = MONTH_NAME_TO_MONTH[month_col]
                            prices["off_peak"][month_num] = price
                        except ValueError:
                            continue

    return prices


def format_plan_name(name: str, max_length: int) -> list[str]:
	"""
	Formats plan name for terminal table output.
	- splits a string into two of equal length.
	- replaces "_" with " " characters
	- upper cases the first character

	Args:
		name (str): The plan to format
		max_length (int): Max length the formatted name should be

	Returns:
		list[str]: a list of length two. Strings are padded to be equal length
	"""
	_name = name.replace('_', ' ')
	_name = _name[:1].upper() + _name[1:]
	if len(_name) <= max_length:
		return [_name, ''.ljust(len(_name))]
	_index_split = _name[0 : max_length].rfind(' ')
	_name1 = _name[:_index_split]
	_name2 = _name[_index_split + 1:].ljust(_index_split)
	_name_length = max(len(_name1), len(_name2))
	return [ _name1.ljust(_name_length), _name2.ljust(_name_length) ]

if __name__ == "__main__":
	# Test with data directory and Powershop prices
	data_dir = "data"
	powershop_prices_path = "powershop_auckland_vector_prices.csv"

	if os.path.exists(data_dir) and os.listdir(data_dir):
		comparator = PlanComparison(data_dir, powershop_prices_path)
		results = comparator.compare()

		# Print results in ASCII table format with wrapped plan names
		print("\nPlan Comparison Results:")
		print("-" * 100)
		# Header with plan names wrapping at 14 characters per column
		plans = list(comparator.PLANS.keys())
		MONTH_WIDTH = 7
		PLAN_MAX_WIDTH = 14

		# Print header
		plan_formatted_names = [format_plan_name(p, PLAN_MAX_WIDTH) for p in plans]
		# First line: Month + first PLAN_MAX_WIDTH chars of each plan name
		line = 'Month  '
		for plan_formatted_name in plan_formatted_names:
			line += '|' + plan_formatted_name[0]
		print(line)

		# Second line: remaining chars of plan names
		line = '       '
		for plan_formatted_name in plan_formatted_names:
			line += '|' + plan_formatted_name[1]
		print(line)
		print("-" * 100)
		# Print each row (data columns use same width as header)
		for row in results:
			month = row['Month']
			month_line = month.ljust(MONTH_WIDTH)
			line = month_line
			for i, plan in enumerate(plans):
				line += '|' + f"${row[plan]:.2f}".rjust(len(plan_formatted_names[i][0]))
			print(line)

		# Also output to CSV
		output_csv = "comparison_results.csv"
		with open(output_csv, 'w', newline='') as f:
			fieldnames = ['Month'] + [p for p in comparator.PLANS.keys()]
			writer = csv.DictWriter(f, fieldnames=fieldnames)
			writer.writeheader()
			writer.writerows(results)
		print(f"\nResults written to {output_csv}")
	else:
		print(f"No data found in {data_dir}")