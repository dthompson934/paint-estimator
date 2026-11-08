# Paint Estimator (v1 proof of concept)

## Run it
    pip install -r requirements.txt
    streamlit run app.py

It opens in your browser. To use it on a phone or iPad on the same Wi-Fi,
open the "Network URL" Streamlit prints in the terminal.

## How it works
Job (customer info) -> Rooms (L x W x H, doors, windows) -> Services.

Each service line = quantity x rate x option multipliers
(x high-ceiling surcharge for height-sensitive services).

Room math: walls = 2 x (L + W) x H minus doors/windows; ceiling = L x W;
perimeter = 2 x (L + W) (used for trim and caulking).

## Changing prices (no code needed)
- data/price_book.csv: one row per service.
  - unit: wall_sqft, ceiling_sqft, perimeter_ft (auto-filled from room size),
    or sqft, linear_ft, each, hour (entered by hand)
  - option_groups: which upgrade choices apply, separated by |
  - height_surcharge: Y if high ceilings make this service cost more
- data/options.csv: upgrade choices and their multipliers (1.15 = +15%).
- data/settings.json: business name/contact, door/window deductions,
  high-ceiling threshold and surcharge.

All prices in these files are placeholders.

## Saving jobs
Use "Save job file" in the sidebar to download a job, and "Open a saved job" to reload it.
