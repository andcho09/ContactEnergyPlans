# Contact Energy Daily Usage Downloader

Downloads Contact Energy electricity usage using [contact-energy-nz](https://github.com/tkhadimullin/contact-energy-nz).

## Usage

**First time set up**

1. Create a Python virtual environment:
	```bash
	python3 -m venv .venv
	```
1. Activate the virtual environment:
	- On Linux/macOS: `source .venv/bin/activate`
	- On Windows: `.venv\Scripts\activate`
1. Install the required dependencies:
	```bash
	pip install -r requirements.txt
	```
1. Create `.env` file with parameters (see `.env.template` for details)
	* `ACCOUNT_ID`
	* `CONTRACT_ID`
	* `TOKEN`

**Downloading usage data**

1. Tweak the start and end dates in [main.py](main.py)
1. Run the downloader

	```bash
	python3 main.py
	```

	Files are saved as .csv to the `data` folder by date.

**Comparing electricity plans**

Once data has been downloaded compare different Contact energy plans:

1. Tweak the plan rates and free or half-price periods in [compare.py](compare.py)
1. Run the comparison

	```bash
	python3 compare.py
	```

## References

* [contact-energy-nz](https://github.com/tkhadimullin/contact-energy-nz)