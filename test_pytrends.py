# test_pytrends.py
import traceback

from pytrends.request import TrendReq


def main():
    try:
        pytrends = TrendReq(hl="en-US", tz=360, retries=2, backoff_factor=0.1)
        queries = ["Taylor Swift", "World Cup"]
        print("Building payload for:", queries)
        pytrends.build_payload(queries, timeframe="now 7-d", geo="US")
        print(
            "interest_over_time_widget keys:",
            list(pytrends.interest_over_time_widget.keys()),
        )
        df = pytrends.interest_over_time()
        if df is None or df.empty:
            print("No data returned (df is empty).")
            return
        print(df.tail(5))
    except Exception:
        print("Exception during pytrends run:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
