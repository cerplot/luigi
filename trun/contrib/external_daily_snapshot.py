
import datetime
import logging

import trun

logger = logging.getLogger('trun-interface')


class ExternalDailySnapshot(trun.ExternalStep):
    """
    Abstract class containing a helper method to fetch the latest snapshot.

    Example::

      class MyStep(trun.Step):
        def requires(self):
          return PlaylistContent.latest()

    All steps subclassing :class:`ExternalDailySnapshot` must have a :class:`trun.DateParameter`
    named ``date``.

    You can also provide additional parameters to the class and also configure
    lookback size.

    Example::

      ServiceLogs.latest(service="radio", lookback=21)

    """
    date = trun.DateParameter()
    __cache = []

    @classmethod
    def latest(cls, *args, **kwargs):
        """This is cached so that requires() is deterministic."""
        date = kwargs.pop("date", datetime.date.today())
        lookback = kwargs.pop("lookback", 14)
        # hashing kwargs deterministically would be hard. Let's just lookup by equality
        key = (cls, args, kwargs, lookback, date)
        for k, v in ExternalDailySnapshot.__cache:
            if k == key:
                return v
        val = cls.__latest(date, lookback, args, kwargs)
        ExternalDailySnapshot.__cache.append((key, val))
        return val

    @classmethod
    def __latest(cls, date, lookback, args, kwargs):
        assert lookback > 0
        t = None
        for i in range(lookback):
            d = date - datetime.timedelta(i)
            t = cls(date=d, *args, **kwargs)
            if t.complete():
                return t
        logger.debug("Could not find last dump for %s (looked back %d days)",
                     cls.__name__, lookback)
        return t
