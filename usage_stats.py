import csv
import os
from datetime import datetime, date
from typing import Dict, List

MONTH_NAME_TO_MONTH = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}


def is_weekend(d: date) -> bool:
    """Check if a date is a weekend (Saturday or Sunday)"""
    return d.weekday() >= 5


def is_weekday(d: date) -> bool:
    """Check if a date is a weekday (Monday to Friday)"""
    return d.weekday() < 5


def _is_in_hour_range(hour: int, start: int, end: int) -> bool:
    """Check if hour is in range [start, end). Note: hour 0-24"""
    if start < end:
        return start <= hour < end
    else:
        # Handles overnight ranges like 21 to 7
        return hour >= start or hour < end


def load_usage_data(data_dir: str) -> Dict[date, List[Dict]]:
    """
    Load all CSV files from the data directory.
    
    Args:
        data_dir: Directory containing CSV files with usage data. Files should be named
            in YYYYMMDD format (e.g., "20250601.csv").
    
    Returns:
        Dictionary mapping date objects to lists of hourly usage dictionaries.
    """
    data: Dict[date, List[Dict]] = {}
    
    if not os.path.exists(data_dir):
        print(f"Data directory '{data_dir}' does not exist.")
        return data
    
    for filename in sorted(os.listdir(data_dir)):
        if filename.endswith('.csv'):
            filepath = os.path.join(data_dir, filename)
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
                
                if parsed_date not in data:
                    data[parsed_date] = []
                data[parsed_date].extend(rows)
    
    return data


def calculate_monthly_stats(data: Dict[date, List[Dict]]) -> List[Dict]:
    """
    Calculate monthly usage statistics.
    
    For each month, calculates:
    - Total kWh usage
    - Percentage of usage spent on weekends
    - Percentage of usage spent on weekends between 9am and 5pm
    
    Args:
        data: Dictionary mapping date objects to lists of hourly usage dictionaries.
    
    Returns:
        List of dictionaries containing monthly statistics.
    """
    # Structure: {month: {total_kwh: float, total_cost: float, weekend_kwh: float, weekend_9am_5pm_kwh: float}}
    monthly_stats: Dict[str, Dict] = {}
    
    # Process each date
    for d in sorted(data.keys()):
        rows = data[d]
        
        # Determine month (using date from data)
        month = d.strftime("%Y-%m")
        
        # Initialize month if not exists
        if month not in monthly_stats:
            monthly_stats[month] = {
                "month": month,
                "total_kwh": 0.0,
                "total_cost": 0.0,
                "weekend_kwh": 0.0,
                "weekend_cost": 0.0,
                "weekend_9am_5pm_kwh": 0.0,
                "weekend_9am_5pm_cost": 0.0,
            }
        
        # Accumulate stats for each row
        for row in rows:
            kwh = row['kwh']
            hour = row['hour']
            date_key = row['date']
            
            # Add to total
            monthly_stats[month]["total_kwh"] += kwh
            monthly_stats[month]["total_cost"] += kwh * row['price']
            
            # Check if weekend
            if is_weekend(date_key):
                monthly_stats[month]["weekend_kwh"] += kwh
                monthly_stats[month]["weekend_cost"] += kwh * row['price']
                
                # Check if in 9am-5pm range (9 to 17, i.e., hours 9, 10, ..., 16)
                if _is_in_hour_range(hour, 9, 17):
                    monthly_stats[month]["weekend_9am_5pm_kwh"] += kwh
                    monthly_stats[month]["weekend_9am_5pm_cost"] += kwh * row['price']
    
    # Calculate percentages
    for month in monthly_stats:
        stats = monthly_stats[month]
        
        # Weekend percentage
        if stats["total_kwh"] > 0:
            stats["weekend_pct"] = (stats["weekend_kwh"] / stats["total_kwh"]) * 100
        else:
            stats["weekend_pct"] = 0.0
        
        # Weekend 9am-5pm percentage
        if stats["total_kwh"] > 0:
            stats["weekend_9am_5pm_pct"] = (stats["weekend_9am_5pm_kwh"] / stats["total_kwh"]) * 100
        else:
            stats["weekend_9am_5pm_pct"] = 0.0
    
    # Get sorted list of unique months
    sorted_months = sorted(monthly_stats.keys())
    
    return [monthly_stats[m] for m in sorted_months]


def print_table(stats: List[Dict]) -> None:
    """Print monthly statistics as a formatted table to console."""
    print("\nMonthly Usage Statistics")
    print("=" * 100)
    
    # Header
    print(f"{'Month':<10} {'Total kWh':>12} {'Weekend %':>12} {'Weekend (9-5pm) %':>20}")
    print("-" * 100)
    
    for stat in stats:
        month = stat["month"][:4] + "-" + stat["month"][5:]  # Format as YYYY-MM
        print(f"{month:<10} {stat['total_kwh']:>12.2f} {stat['weekend_pct']:>10.2f}% {stat['weekend_9am_5pm_pct']:>18.2f}%")
    
    print("-" * 100)
    
    # Calculate and print totals
    total_kwh = sum(s["total_kwh"] for s in stats)
    total_weekend_kwh = sum(s["weekend_kwh"] for s in stats)
    total_weekend_9am_5pm_kwh = sum(s["weekend_9am_5pm_kwh"] for s in stats)
    
    if total_kwh > 0:
        total_weekend_pct = (total_weekend_kwh / total_kwh) * 100
        total_weekend_9am_5pm_pct = (total_weekend_9am_5pm_kwh / total_kwh) * 100
    else:
        total_weekend_pct = 0.0
        total_weekend_9am_5pm_pct = 0.0
    
    print(f"{'Total':<10} {total_kwh:>12.2f} {total_weekend_pct:>10.2f}% {total_weekend_9am_5pm_pct:>18.2f}%")
    print()


def write_csv(stats: List[Dict], csv_path: str) -> None:
    """Write monthly statistics to a CSV file."""
    fieldnames = [
        "month",
        "total_kwh",
        "total_cost",
        "weekend_kwh",
        "weekend_cost",
        "weekend_9am_5pm_kwh",
        "weekend_9am_5pm_cost",
        "weekend_pct",
        "weekend_9am_5pm_pct",
    ]
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for stat in stats:
            writer.writerow(stat)
    
    print(f"Results written to {csv_path}")


def main():
    """Main function to run usage stats analysis."""
    data_dir = "data"
    output_csv = "usage_stats.csv"
    
    # Load data
    print(f"Loading usage data from '{data_dir}'...")
    data = load_usage_data(data_dir)
    
    if not data:
        print("No data found.")
        return
    
    print(f"Loaded {len(data)} days of data.")
    
    # Calculate statistics
    print("Calculating monthly statistics...")
    stats = calculate_monthly_stats(data)
    print(f"Calculated statistics for {len(stats)} months.")
    
    # Print table
    print_table(stats)
    
    # Write CSV
    write_csv(stats, output_csv)


if __name__ == "__main__":
    main()