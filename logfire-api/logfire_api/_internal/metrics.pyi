import dataclasses
from _typeshed import Incomplete
from abc import ABC
from opentelemetry.metrics import CallbackT as CallbackT, Counter, Histogram, Instrument, Meter, MeterProvider, ObservableCounter, ObservableGauge, ObservableUpDownCounter, UpDownCounter, _Gauge
from opentelemetry.util.types import Attributes
from threading import Lock
from typing import Any, Generic, Sequence, TypeVar
from weakref import WeakSet

Gauge: Incomplete

@dataclasses.dataclass
class ProxyMeterProvider(MeterProvider):
    provider: MeterProvider
    meters: WeakSet[_ProxyMeter] = ...
    lock: Lock = ...
    def get_meter(self, name: str, version: str | None = None, schema_url: str | None = None, *args: Any, **kwargs: Any) -> Meter: ...
    def set_meter_provider(self, meter_provider: MeterProvider) -> None: ...
    def shutdown(self, timeout_millis: float = 30000) -> None: ...
    def force_flush(self, timeout_millis: float = 30000) -> None: ...

class _ProxyMeter(Meter):
    def __init__(self, meter: Meter, name: str, version: str | None, schema_url: str | None) -> None: ...
    def set_meter(self, meter_provider: MeterProvider) -> None:
        """Called when a real meter provider is set on the creating _ProxyMeterProvider.

        Creates a real backing meter for this instance and notifies all created
        instruments so they can create real backing instruments.
        """
    def create_counter(self, name: str, unit: str = '', description: str = '') -> Counter: ...
    def create_up_down_counter(self, name: str, unit: str = '', description: str = '') -> UpDownCounter: ...
    def create_observable_counter(self, name: str, callbacks: Sequence[CallbackT] | None = None, unit: str = '', description: str = '') -> ObservableCounter: ...
    def create_histogram(self, name: str, unit: str = '', description: str = '') -> Histogram: ...
    def create_gauge(self, name: str, unit: str = '', description: str = '') -> _Gauge: ...
    def create_observable_gauge(self, name: str, callbacks: Sequence[CallbackT] | None = None, unit: str = '', description: str = '') -> ObservableGauge: ...
    def create_observable_up_down_counter(self, name: str, callbacks: Sequence[CallbackT] | None = None, unit: str = '', description: str = '') -> ObservableUpDownCounter: ...
InstrumentT = TypeVar('InstrumentT', bound=Instrument)

class _ProxyInstrument(ABC, Generic[InstrumentT]):
    def __init__(self, instrument: InstrumentT, name: str, unit: str, description: str) -> None: ...
    def on_meter_set(self, meter: Meter) -> None:
        """Called when a real meter is set on the creating _ProxyMeter."""

class _ProxyAsynchronousInstrument(_ProxyInstrument[InstrumentT], ABC):
    def __init__(self, instrument: InstrumentT, name: str, callbacks: Sequence[CallbackT] | None, unit: str, description: str) -> None: ...

class _ProxyCounter(_ProxyInstrument[Counter], Counter):
    def add(self, amount: int | float, attributes: Attributes | None = None, *args: Any, **kwargs: Any) -> None: ...

class _ProxyHistogram(_ProxyInstrument[Histogram], Histogram):
    def record(self, amount: int | float, attributes: Attributes | None = None, *args: Any, **kwargs: Any) -> None: ...

class _ProxyObservableCounter(_ProxyAsynchronousInstrument[ObservableCounter], ObservableCounter): ...
class _ProxyObservableGauge(_ProxyAsynchronousInstrument[ObservableGauge], ObservableGauge): ...
class _ProxyObservableUpDownCounter(_ProxyAsynchronousInstrument[ObservableUpDownCounter], ObservableUpDownCounter): ...

class _ProxyUpDownCounter(_ProxyInstrument[UpDownCounter], UpDownCounter):
    def add(self, amount: int | float, attributes: Attributes | None = None, *args: Any, **kwargs: Any) -> None: ...

class _ProxyGauge(_ProxyInstrument[Gauge], Gauge):
    def set(self, amount: int | float, attributes: Attributes | None = None, *args: Any, **kwargs: Any) -> None: ...
