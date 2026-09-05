"""Validate a real Yahoo one-minute session and prepare a traceable music score.

Usage: python analyze_session.py --date 2026-09-04
Uses the saved source by default. --fetch explicitly retrieves a fresh snapshot.
No forecasts, inferred news causes, broker calls, or orders.
"""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import numpy as np

SOURCE = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=5d&interval=1m&includePrePost=false"
ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]


def scaled(values):
    values = np.asarray(values, dtype=float)
    a, b = np.percentile(values, [10, 90])
    return np.clip((values-a)/(b-a), 0, 1) if b > a else np.zeros_like(values)


def clock(minute):
    return (datetime(2000, 1, 1, 9, 30)+timedelta(minutes=float(minute))).strftime("%H:%M")


def song_clock(minute):
    seconds = minute/2
    return f"{int(seconds//60)}:{seconds%60:04.1f}"


def analyze(path, date):
    raw = path.read_bytes()
    document = json.loads(raw)
    if document["chart"].get("error"):
        raise ValueError(document["chart"]["error"])
    result = document["chart"]["result"][0]
    meta = result["meta"]
    assert meta["symbol"] == "SPY", "Wrong instrument"
    assert meta["exchangeTimezoneName"] == "America/New_York", "Unexpected exchange time zone"
    start = datetime.combine(datetime.fromisoformat(date).date(), time(9, 30), ET)
    end = start + timedelta(minutes=390)
    assert end <= datetime.now(timezone.utc), "Cannot analyze an unfinished full session"
    expected = [int((start+timedelta(minutes=i)).timestamp()) for i in range(390)]
    quotes = result["indicators"]["quote"][0]
    rows = []
    seen = set()
    for i, ts in enumerate(result["timestamp"]):
        if not int(start.timestamp()) <= ts < int(end.timestamp()):
            continue
        assert ts not in seen, f"Duplicate timestamp: {ts}"
        seen.add(ts)
        row = {k: quotes[k][i] for k in ("open", "high", "low", "close", "volume")}
        assert all(v is not None and math.isfinite(v) for v in row.values()), f"Missing/nonfinite bar: {ts}"
        assert row["low"] > 0 and row["high"] >= max(row["open"], row["close"]) >= row["low"], f"Invalid OHLC: {ts}"
        assert row["low"] <= min(row["open"], row["close"]) and row["volume"] >= 0, f"Invalid OHLCV: {ts}"
        row.update(timestamp=ts, timestamp_et=datetime.fromtimestamp(ts, ET).isoformat(), minute=int((ts-start.timestamp())//60))
        rows.append(row)
    rows.sort(key=lambda r: r["timestamp"])
    assert [r["timestamp"] for r in rows] == expected, "Session must contain exactly 390 consecutive one-minute bars, 09:30 through 15:59 ET. No filling gaps."
    closing_print = None
    for i, ts in enumerate(result["timestamp"]):
        if ts == int(end.timestamp()) and quotes["close"][i] is not None:
            closing_print = dict(timestamp=ts,timestamp_et=end.isoformat(),close=float(quotes["close"][i]),
                note="Separate vendor 16:00 price observation; not an extra regular-session minute or an inferred auction volume.")
    close = np.array([r["close"] for r in rows])
    highs = np.array([r["high"] for r in rows])
    lows = np.array([r["low"] for r in rows])
    volume = np.array([r["volume"] for r in rows])
    prices = np.r_[rows[0]["open"], close]
    last_minute_close=float(prices[-1])
    if closing_print:
        prices[-1]=closing_print["close"]
    day_low, day_high = float(lows.min()), float(highs.max())
    energy = scaled(np.log1p(volume))
    ranges = (highs-lows)/close*10000
    volatility = scaled(np.array([np.mean(ranges[max(0,i-4):i+1]) for i in range(390)]))
    for i, row in enumerate(rows):
        row.update(price_position=float((close[i]-day_low)/(day_high-day_low)) if day_high > day_low else .5,
                   energy=float(energy[i]), volatility=float(volatility[i]),
                   return_bps=float((close[i]/prices[i]-1)*10000), range_bps=float(ranges[i]))

    # Descriptive segmentation: repeatedly split the straight-line approximation
    # at its largest residual. Keep legs >= 18 minutes; five-minute smoothing
    # is for segmentation only. Raw one-minute observations drive the music.
    smooth = np.convolve(np.pad(prices, (2,2), mode="edge"), np.ones(5)/5, mode="valid")
    pivots = [0,390]
    while len(pivots) < 8:
        candidates=[]
        for a,b in zip(pivots,pivots[1:]):
            if b-a < 36:
                continue
            x=np.arange(a+18,b-17)
            residual=np.abs(smooth[x] - (smooth[a]+(smooth[b]-smooth[a])*(x-a)/(b-a)))
            j=int(np.argmax(residual))
            candidates.append((float(residual[j]),int(x[j])))
        if not candidates:
            break
        _, split=max(candidates)
        pivots=sorted(pivots+[split])

    sections=[]
    for j,(a,b) in enumerate(zip(pivots,pivots[1:]),1):
        change=float((prices[b]/prices[a]-1)*100)
        direction="rising" if change>.025 else "falling" if change<-.025 else "sideways"
        sections.append(dict(name=f"Leg {j}: {direction}", start_minute=a,end_minute=b,
            start_et=clock(a),end_et=clock(b),song_start=song_clock(a),song_end=song_clock(b),
            start_price=float(prices[a]),end_price=float(prices[b]),return_pct=change,
            average_energy=float(energy[a:b].mean()),average_volatility=float(volatility[a:b].mean())))

    blocks=[]
    for a in range(0,390,30):
        b=a+30
        blocks.append(dict(start_et=clock(a),end_et=clock(b),open=float(rows[a]["open"]),close=float(prices[b]),
            change_pct=float((prices[b]/rows[a]["open"]-1)*100),volume=int(volume[a:b].sum()),
            high=float(highs[a:b].max()),low=float(lows[a:b].min())))
    high_i=int(np.argmax(highs)); low_i=int(np.argmin(lows))
    running=np.maximum.accumulate(prices)
    summary=dict(open=float(prices[0]),close=float(prices[-1]),last_minute_bar_close=last_minute_close,open_to_close_pct=float((prices[-1]/prices[0]-1)*100),
        high=day_high,high_bar_et=clock(high_i),low=day_low,low_bar_et=clock(low_i),
        range_pct_of_open=float((day_high-day_low)/prices[0]*100),volume=int(volume.sum()),
        close_position_in_range=float((prices[-1]-day_low)/(day_high-day_low)) if day_high>day_low else .5,
        max_close_to_close_drawdown_pct=float(np.min((prices/running-1)*100)),
        largest_up_minute=rows[int(np.argmax([r["return_bps"] for r in rows]))],
        largest_down_minute=rows[int(np.argmin([r["return_bps"] for r in rows]))])
    output=dict(schema="malosound.session-to-song.v1",symbol="SPY",date=date,
        session_start=start.isoformat(),session_end=end.isoformat(),bar_timestamp_convention="bar start; 15:59 bar ends at 16:00",
        duration_seconds=195,tempo_bpm=80,source_url=SOURCE,source_sha256=hashlib.sha256(raw).hexdigest(),
        snapshot_saved_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
        validation=dict(expected_bars=390,observed_bars=len(rows),missing_bars=0,duplicate_bars=0,imputed_bars=0,
            timezone="America/New_York",regular_session_only=True,exchange_certified=False),
        interpretation_scope="Retrospective musical interpretation of public vendor minute bars; no forecast or trade recommendation. Intraminute path is unknown.",
        normalization="Price position uses full-session high/low; volume uses clipped 10th–90th percentile log volume; volatility uses trailing five-minute mean range bps, clipped to session 10th–90th percentile. All are retrospective, relative within this session.",
        closing_print=closing_print,
        mapping=dict(time="390 minutes -> 195 seconds; 1 minute -> 0.5 second",tempo="80 BPM, 65 four-beat bars; each bar spans six market minutes",
            pitch="Monotonic D-minor-pentatonic mapping from session-relative price position",energy="Relative observed minute volume",texture="Observed minute range / price, smoothed over trailing five minutes",
            artistic_choices=["D minor", "80 BPM", "Instrument voices", "Rhythm and harmony"],
            limitation="Full-day normalization and retrospective segments cannot be used as a pre-open signal; normalization hides absolute differences in range and volume across days."),
        summary=summary,sections=sections,half_hour_blocks=blocks,minutes=rows)
    daily_path=path.parent/"source-yahoo-daily.json"
    if daily_path.exists():
        daily_raw=daily_path.read_bytes()
        daily=json.loads(daily_raw)["chart"]["result"][0]
        matches=[i for i,t in enumerate(daily["timestamp"]) if datetime.fromtimestamp(t,ET).date()==start.date()]
        assert len(matches)==1, "Daily cross-check does not contain the requested date"
        i=matches[0]
        daily_bar={k:float(v[i]) for k,v in daily["indicators"]["quote"][0].items()}
        for key in ("open","high","low"):
            assert abs(daily_bar[key]-summary[key])<.02, f"Daily {key} disagrees with minute bars"
        output["daily_reconciliation"]=dict(source_sha256=hashlib.sha256(daily_raw).hexdigest(),
            source_url="https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=5d&interval=1d&includePrePost=false",
            daily_ohlcv=daily_bar,minute_volume_sum=int(volume.sum()),
            minute_volume_fraction_of_daily=float(volume.sum()/daily_bar["volume"]) if daily_bar["volume"]>0 else None,
            last_minute_close_difference=float(last_minute_close-daily_bar["close"]),
            ending_price_difference=float(summary["close"]-daily_bar["close"]),
            caveat="Minute timestamps are complete, but their summed volume differs from the vendor daily total. No missing volume is allocated to bars. Dynamics use observed minute volume only. The same vendor daily check is a consistency check, not independent exchange verification.")
    composition_path=path.parent/"llm-composition.json"
    if composition_path.exists():
        composition=json.loads(composition_path.read_text(encoding="utf-8"))
        assert composition["date"]==date and composition["symbol"]=="SPY"
        cs=composition["sections"]
        assert cs[0]["start_minute"]==0 and cs[-1]["end_minute"]==390
        assert all(a["end_minute"]==b["start_minute"] for a,b in zip(cs,cs[1:])), "Composition gaps or overlaps"
        output["composition"]=composition
    target=path.parent/"analysis.json"
    target.write_text(json.dumps(output,indent=2),encoding="utf-8")
    with (path.parent/"spy-1minute.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date",required=True)
    p.add_argument("--source",type=Path,default=ROOT/"Song Journal"/"source-yahoo-chart.json")
    p.add_argument("--fetch",action="store_true")
    args=p.parse_args()
    if args.fetch:
        args.source.parent.mkdir(parents=True,exist_ok=True)
        with urlopen(Request(SOURCE,headers={"User-Agent":"Mozilla/5.0"}),timeout=30) as response:
            args.source.write_bytes(response.read())
    output=analyze(args.source,args.date)
    print(json.dumps({k:output[k] for k in ["date","validation","summary","sections","half_hour_blocks"]},indent=2))


if __name__=="__main__":
    main()
