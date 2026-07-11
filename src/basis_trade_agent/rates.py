from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class RateSample:
    timestamp: datetime
    rateAprPercent: float


class RateHistory:
    def __init__(self, windowHours: float) -> None:
        self.windowHours = windowHours
        self.samples: list[RateSample] = []

    def append(self, timestamp: datetime, rateAprPercent: float) -> None:
        cutoff = timestamp - timedelta(hours=self.windowHours)
        self.samples = [sample for sample in self.samples if sample.timestamp >= cutoff]
        self.samples.append(RateSample(timestamp=timestamp, rateAprPercent=rateAprPercent))

    def smoothed_rate(self) -> float:
        return sum(sample.rateAprPercent for sample in self.samples) / len(self.samples)
