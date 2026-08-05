# Contact Energy Daily Usage Downloader

Downloads Contact Energy electricity usage using [contact-energy-nz](https://github.com/tkhadimullin/contact-energy-nz).

## Usage

**First time set up**

1. Create a Python virtual environment:
	```bash
	python3 -m venv .venv
	```
2. Activate the virtual environment:
	- On Linux/macOS: `source .venv/bin/activate`
	- On Windows: `.venv\Scripts\activate`
3. Install the required dependencies:
	```bash
	pip install -r requirements.txt
	```
4. Create `.env` file with parameters (see `.env.template` for details)
	* `ACCOUNT_ID`
	* `CONTRACT_ID`
	* `TOKEN` (or `USERNAME`/`PASSWORD` as an alternative authentication method)

**Downloading usage data**

1. Tweak the start and end dates in [main.py](main.py)
2. Run the downloader

	```bash
	python3 main.py
	```

	Files are saved as .csv to the `data` folder by date.

**Analysing usage patterns**

Once data has been downloaded, analyse your monthly usage to help pick the best plan:

```bash
python3 usage_stats.py
```

This prints a table of monthly totals, weekend usage, and weekend 9am-5pm usage, and writes the same figures to `usage_stats.csv`.

**Comparing electricity plans**

Once data has been downloaded compare different Contact, Powershop and Genesis plans:

1. Tweak the plan rates and free or half-price periods in [compare.py](compare.py)
2. If needed, update the provider price source CSVs (`powershop_auckland_vector_prices.csv`, `genesis_auckland_prices.csv`, `genesis_low_user_auckland_prices.csv`) referenced by the `source` keys in the `PLANS` config
3. Run the comparison

	```bash
	python3 compare.py
	```

The results are printed to the console as a table and written to `comparison_results.csv`.

## References

* [contact-energy-nz](https://github.com/tkhadimullin/contact-energy-nz)