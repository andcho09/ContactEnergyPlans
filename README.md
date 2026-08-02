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

## References