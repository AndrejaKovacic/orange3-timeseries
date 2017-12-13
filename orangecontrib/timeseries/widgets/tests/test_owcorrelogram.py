import unittest

import numpy as np

from Orange.data import Domain, ContinuousVariable
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owcorrelogram import OWCorrelogram


class TestCorrelogramWidget(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWCorrelogram)  # type: OWCorrelogram

    def test_nan_timeseries(self):
        """
        Widget used to crash because interpolation crashed when
        there was a column with all nans or all nuns and only one number.
        Now interpolation is skipped.
        GH-27
        """
        time_series = Timeseries(
            Domain(attributes=[ContinuousVariable("a"), ContinuousVariable("b")]),
            list(zip(list(range(5)), list(range(5))))
        )
        time_series.X[:, 1] = np.nan
        self.send_signal(self.widget.Inputs.time_series, time_series)
        time_series.X[2, 1] = 42
        self.send_signal(self.widget.Inputs.time_series, time_series)


if __name__ == "__main__":
    unittest.main()
