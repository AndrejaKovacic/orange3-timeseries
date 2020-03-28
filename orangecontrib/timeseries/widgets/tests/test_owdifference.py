import unittest
from unittest.mock import Mock

import numpy as np

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest
from orangecontrib.timeseries.widgets.owdifference import OWDifference

class TestOWDifference(WidgetTest):
    
    def setUp(self):
        self.widget = self.create_widget(OWDifference)
        self.widget.autocommit = True
        self.data = Table('iris')

    def test_difference(self):
        w = self.widget
        w.calc_difference = True
        w.diff_order = 1
        w.shift_period = 1
        self.send_signal(w.Inputs.time_series, self.data[:6])
        w.selected = ['petal width']
        w.commit()
        out = self.get_output(w.Outputs.time_series).X[:, -1]
        true_out = np.asarray([np.nan, 0, 0, 0, 0, -0.2])
        np.testing.assert_array_equal(out, true_out)

        # test order always one, if shift > 1
        w.shift_period = 2
        w.diff_order = 5
        self.send_signal(w.Inputs.time_series, self.data[:6])
        w.selected = ['petal width']
        w.commit()
        out = self.get_output(w.Outputs.time_series).X[:, -1]
        true_out = np.asarray([np.nan, np.nan, 0, 0, 0, -0.2])
        np.testing.assert_array_equal(out, true_out)

    def test_qoutient(self):
        w = self.widget
        w.calc_difference = False
        w.invert_direction = False
        w.shift_period = 1
        self.send_signal(w.Inputs.time_series, self.data[:6])
        w.selected = ['petal width']
        w.commit()
        out = self.get_output(w.Outputs.time_series).X[:, -1]
        true_out = np.asarray([1, 1, 1, 1, 2, np.nan])
        np.testing.assert_array_equal(out, true_out)

    def test_order_spin(self):
        w = self.widget
        w.calc_difference = True
        w.shift_period = 1
        w.on_changed()
        self.assertTrue(w.order_spin.isEnabled())

        w.shift_period = 2
        w.on_changed()
        self.assertFalse(w.order_spin.isEnabled())
        
        w.shift_period = 1
        w.on_changed()
        self.assertTrue(w.order_spin.isEnabled())

        w.calc_difference = False
        w.on_changed()
        self.assertFalse(w.order_spin.isEnabled())
        
        w.calc_difference = True
        w.on_changed()
        self.assertTrue(w.order_spin.isEnabled())

if __name__ == "__main__":
    unittest.main()
