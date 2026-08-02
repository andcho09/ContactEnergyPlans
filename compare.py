import csv
import os
from datetime import datetime, date
from typing import Dict, List

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
	"""

	# Plan pricing configuration (ex GST)
	# All rates are per kWh except daily_charge which is per day
	PLANS = {
		"standard": {
			"rate": 0.244,         # $/kWh
			"levy": 0.0019,        # $/kWh
			"daily_charge": 2.801, # $/day
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
		"good_nights": {
			"rate": 0.293,          # $/kWh
			"levy": 0,              # $/kWh
			"daily_charge": 3.0001, # $/day
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
	}

	def __init__(self, data_dir: str):
		"""Load .csv files from the data_dir which are named by date into a list of rows
		containing date, hour, usage (in kwh)

		Args:
			data_dir: Directory containing CSV files with usage data. Files should be named
				in YYYYMMDD format (e.g., "20250601.csv").

		Note:
			The data is stored in self.data as a dictionary mapping dates to lists of row dictionaries.
			Each row contains: hour, kwh, price, uncharged_kwh, offpeak_kwh, offpeak_price, date
		"""

		self.data_dir = data_dir
		self.data: Dict[date, List[Dict]] = {}

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
							def safe_float(key, default=0.0):
								val = row.get(key, default)
								if isinstance(val, str):
									val = val.strip()
									return float(val) if val else default
								return float(val) if val else default
							row['uncharged_kwh'] = safe_float('uncharged_kwh')
							row['offpeak_kwh'] = safe_float('offpeak_kwh')
							row['offpeak_price'] = safe_float('offpeak_price')
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

	def _is_in_hour_range(self, hour: int, start: int, end: int) -> bool:
		"""Check if hour is in range [start, end). Note: hour 0-24"""
		if start < end:
			return start <= hour < end
		else:
			# Handles overnight ranges like 21 to 7
			return hour >= start or hour < end

	def is_half_price_period(self, hour: int, d: date, plan: str) -> bool:
		"""Check if the given hour falls within a half-price period for this plan"""
		if plan not in self.PLANS:
			return False

		_plan = self.PLANS[plan]
		for start_hour, end_hour in _plan.get("half_price_periods", []):
			if self._is_in_hour_range(hour, start_hour, end_hour):
				return True
		return False

	def calculate_hourly_cost(self, row: Dict, plan: str) -> float:
		"""Calculate cost for a single hour of usage under a given plan"""
		kwh = row['kwh']
		hour = row['hour']

		base_rate = self.PLANS[plan]["rate"]
		levy = self.PLANS[plan]["levy"]

		# Check if free period (completely free power)
		if self.is_free_period(hour, row['date'], plan):
			return 0.0

		# Check if half-price period
		if self.is_half_price_period(hour, row['date'], plan):
			rate = base_rate / 2
		else:
			rate = base_rate

		# Cost for this hour: kwh divided by 24 hours to get hourly usage, times rate
		hourly_cost = kwh * (rate + levy)
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
		"""
		if not self.data:
			return []

		# Get date range
		sorted_dates = sorted(self.data.keys())
		first_date = sorted_dates[0]
		last_date = sorted_dates[-1]

		# Group by month: structure is {month_name: {plan_name: cost}}
		monthly_costs: Dict[str, Dict[str, float]] = {}

		# Process each date
		for d in sorted_dates:
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
			row = {'Month': m}
			for plan_name in self.PLANS.keys():
				# Show actual cost for each plan
				row[plan_name] = round(monthly_costs[m][plan_name], 2)

			output_rows.append(row)

		# Add total row
		total_row = {'Month': 'total'}
		for plan_name in self.PLANS.keys():
			total_row[plan_name] = round(sum(monthly_costs[m][plan_name] for m in monthly_costs.keys()), 2)

		output_rows.append(total_row)

		return output_rows


if __name__ == "__main__":
	# Test with data directory
	data_dir = "data"
	if os.path.exists(data_dir) and os.listdir(data_dir):
		comparator = PlanComparison(data_dir)
		results = comparator.compare()

		# Print results
		print("Plan Comparison Results:")
		print("-" * 100)
		for row in results:
			month = row['Month']
			parts = []
			for plan_name, value in row.items():
				if plan_name != 'Month':
					parts.append(f"{plan_name}: ${value:.2f}")
			print(f"{month}: " + ", ".join(parts))
		print("-" * 100)

		# Also output to CSV
		output_csv = "comparison_results.csv"
		with open(output_csv, 'w', newline='') as f:
			writer = csv.DictWriter(f, fieldnames=['Month'] + list(PlanComparison.PLANS.keys()))
			writer.writeheader()
			writer.writerows(results)
		print(f"\nResults written to {output_csv}")
	else:
		print(f"No data found in {data_dir}")