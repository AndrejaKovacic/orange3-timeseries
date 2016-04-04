from json import dumps as json

from collections import defaultdict
from collections.abc import MutableMapping, Mapping, Set, Sequence
import numpy as np

from os.path import join, dirname

from PyQt4.QtCore import Qt, QUrl, QSize, QObject, pyqtProperty, pyqtSlot
from PyQt4.QtGui import QWidget, QSizePolicy
from PyQt4.QtWebKit import QWebView


class WebView(QWebView):
    def __init__(self, parent=None, bridge=None, debug=False, **kwargs):
        """Construct a new QWebView widget that has no history and
        supports loading from local URLs.

        Parameters
        ----------
        parent: QWidget
            The parent widget.
        bridge: QObject
            The QObject to use as a parent. This object is also exposed
            as ``window.pybridge`` in JavaScript.
        """
        super().__init__(parent,
                         sizePolicy=QSizePolicy(QSizePolicy.Expanding,
                                                QSizePolicy.Expanding),
                         sizeHint=QSize(500, 400),
                         contextMenuPolicy=Qt.DefaultContextMenu,
                         **kwargs)
        self.bridge = bridge
        self.frame = frame = self.page().mainFrame()
        frame.javaScriptWindowObjectCleared.connect(
            lambda: setattr(self, 'frame', self.page().mainFrame()))
        frame.javaScriptWindowObjectCleared.connect(
            lambda: frame.addToJavaScriptWindowObject('pybridge', bridge))

        history = self.history()
        history.setMaximumItemCount(0)
        settings = self.settings()
        settings.setMaximumPagesInCache(0)
        settings.setAttribute(settings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(settings.LocalContentCanAccessRemoteUrls, False)
        if debug:
            settings.setAttribute(settings.LocalStorageEnabled, True)
            settings.setAttribute(settings.DeveloperExtrasEnabled, True)
            settings.setObjectCacheCapacities(4e6, 4e6, 4e6)
            settings.enablePersistentStorage()

    def setContent(self, data, mimetype, base_url=''):
        """Set the content `data` of type `mimetype` in the current webframe."""
        super().setContent(data, mimetype, QUrl(base_url))

    def dropEvent(self, event):
        pass  # Prevent loading of drag-and-drop dropped file

    def evalJS(self, code):
        """Evaluate JavaScript code `code` in the current webframe and
        return the result of the last executed statement."""
        return self.frame.evaluateJavaScript(code)

    def setHtml(self, html, base_url=''):
        """Set the HTML content of the current webframe to html."""
        self.setContent(html.encode('utf-8'), 'text/html', base_url)

    def svg(self):
        """Return SVG string of the first SVG element on the page, or
        raise ValueError if not any.
        """
        html = self.frame.toHtml()
        return html[html.index('<svg '):html.index('</svg>') + 5]

    def clear(self):
        """Clear current page by setting HTML to ''."""
        self.setHtml('')


def _Autotree():
    return defaultdict(_Autotree)


def _to_primitive_types(d):
    if isinstance(d, np.integer):
        return int(d)
    if isinstance(d, np.floating):
        return float(d)
    if isinstance(d, (str, int, float, bool)):
        return d
    if isinstance(d, np.ndarray):
        return d.tolist()
    if isinstance(d, Mapping):
        return {k: _to_primitive_types(d[k]) for k in d}
    if isinstance(d, Set):
        return {k: 1 for k in d}
    if isinstance(d, Sequence):
        return [_to_primitive_types(i) for i in d]
    raise TypeError


def _merge_dicts(d1, d2):
    """Merge dicts recursively in place (``d1`` is modified)"""
    for k, v in d1.items():
        if k in d2:
            if isinstance(v, MutableMapping) and isinstance(d2[k], MutableMapping):
                d2[k] = _merge_dicts(v, d2[k])
    d1.update(d2)
    return d1


def _kwargs_options(kwargs):
    """Transforma a dict into a hierarchical dict.

    Example
    -------
    >>> (_kwargs_options(dict(a_b_c=1, a_d_e=2, x=3)) ==
    ...  dict(a=dict(b=dict(c=1), d=dict(e=2)), x=3))
    True
    """
    kwoptions = _Autotree()
    for kws, val in kwargs.items():
        cur = kwoptions
        kws = kws.split('_')
        for kw in kws[:-1]:
            cur = cur[kw]
        cur[kws[-1]] = val
    return kwoptions


class Highchart(WebView):
    """
    Parameters
    ----------
    parent: QObject
        Qt parent object, if any.
    bridge: QObject
        Exposed as ``window.pybridge`` in JavaScript.
    options: dict
        Default options for this chart. See Highcharts docs. Some
        options are already set in the default theme.
    highchart: str
        One of `Chart`, `StockChart`, or `Map` Highcharts JS types.
    enable_zoom: bool
        Enables scroll wheel zooming and right-click zoom reset.
    enable_select: str
        If '+', allow series' points to be selected by clicking
        on the markers, bars or pie slices. Can also be one of
        'x', 'y', or 'xy' (all of which can also end with '+' for the
        above), in which case it indicates the axes on which
        to enable rectangle selection. The list of selected points
        for each input series (i.e. a list of arrays) is
        passed to the ``selection_callback``.
        Each selected point is represented as its index in the series.
        If the selection is empty, the callback parameter is a single
        empty list.
    javascript: str
        Additional JavaScript code to evaluate beforehand. If you
        need something exposed in the global namespace,
        assign it as an attribute to the ``window`` object.
    debug: bool
        Enables right-click context menu and inspector tools.
    **kwargs:
        The additional options. The underscores in argument names imply
        hierarchy, e.g., keyword argument such as ``chart_type='area'``
        results in the following object, in JavaScript::

            {
                chart: {
                    type: 'area'
                }
            }

        The original `options` argument is updated with options from
        these kwargs-derived objects.
    """

    _HIGHCHARTS_HTML = join(join(dirname(__file__), '_highcharts'), 'chart.html')

    def __init__(self,
                 parent=None,
                 bridge=None,
                 options=None,
                 *,
                 highchart='Chart',
                 enable_zoom=False,
                 enable_select=False,
                 selection_callback=None,
                 javascript='',
                 debug=False,
                 **kwargs):
        options = (options or {}).copy()
        enable_select = enable_select or ''

        if not isinstance(options, dict):
            raise ValueError('options must be dict')
        if enable_select not in ('', '+', 'x', 'y', 'xy', 'x+', 'y+', 'xy+'):
            raise ValueError("enable_select must be '+', 'x', 'y', or 'xy'")
        if enable_select and not selection_callback:
            raise ValueError('enable_select requires selection_callback')

        super().__init__(parent, bridge,
                         debug=debug,
                         url=QUrl(self._HIGHCHARTS_HTML))
        self.debug = debug
        self.highchart = highchart
        self.enable_zoom = enable_zoom
        enable_point_select = '+' in enable_select
        enable_rect_select = enable_select.replace('+', '')
        if enable_zoom:
            _merge_dicts(options, _kwargs_options(dict(
                mapNavigation_enableMouseWheelZoom=True,
                mapNavigation_enableButtons=False)))
        if enable_select:
            self._selection_callback = selection_callback
            self.frame.addToJavaScriptWindowObject('__highchart', self)
            _merge_dicts(options, _kwargs_options(dict(
                chart_events_click='/**/unselectAllPoints/**/')))
        if enable_point_select:
            _merge_dicts(options, _kwargs_options(dict(
                plotOptions_series_allowPointSelect=True,
                plotOptions_series_point_events_click='/**/clickedPointSelect/**/')))
        if enable_rect_select:
            _merge_dicts(options, _kwargs_options(dict(
                chart_zoomType=enable_rect_select,
                chart_events_selection='/**/rectSelectPoints/**/')))
        if kwargs:
            _merge_dicts(options, _kwargs_options(kwargs))

        self.frame.loadFinished.connect(
            lambda: self._evalJS('''
                {javascript};
                var options = {options};
                _fixupOptionsObject(options);
                Highcharts.setOptions(options);
                '''.format(javascript=javascript,
                           options=json(options))))

    def contextMenuEvent(self, event):
        if self.enable_zoom:
            self.evalJS('chart.zoomOut();')
        if self.debug:
            super().contextMenuEvent(event)

    # TODO: left-click select http://jsfiddle.net/gh/get/jquery/1.7.2/highslide-software/highcharts.com/tree/master/samples/highcharts/chart/events-selection-points/

    class _Options(QObject):
        """
        This class hopefully prevent options data from being marshalled
        into a string-like-dumb object. Instead, the mechanism makes it
        available as ``window.pydata.options`` in JavaScript.
        """
        @pyqtProperty('QVariantMap')
        def options(self):
            return self._options

    def exposeObject(self, name, obj):
        """Expose the object `obj` as ``window.<name>`` in JavaScript.

        If the object contains any string values that start and end with
        literal ``/**/``, those are evaluated as JS expressions the result
        value replaces the string in the object.

        The exposure, as defined here, represents a snapshot of object at
        the time of execution. Any future changes on the original Python
        object are not (necessarily) visible in its JavaScript counterpart.

        Parameters
        ----------
        name: str
            The global name the object is exposed as.
        obj: object
            The object to expose. Must contain only primitive types, such as:
            int, float, str, bool, list, dict, set, numpy.ndarray.
        """
        if not isinstance(obj, Mapping):
            raise TypeError('top level object must be a dict')
        try:
            obj = _to_primitive_types(obj)
        except TypeError:
            raise TypeError('object must consist of primitive types (allowed: '
                            'int, float, str, bool, list, dict, set, numpy.ndarray)')

        pydata = self._pydata = self._Options()
        pydata._options = obj
        self.frame.addToJavaScriptWindowObject('_' + name, pydata)
        self._evalJS('''
            window.{0} = window._{0}.options;
            _fixupOptionsObject({0});
        '''.format(name))

    def chart(self, options=None, *,
              highchart=None, javascript='', javascript_after='', **kwargs):
        """ Populate the webview with a new Highcharts JS chart.

        Parameters
        ----------
        options, highchart, javascript, **kwargs:
            The parameters are the same as for the object constructor.
        javascript_after: str
            Same as `javascript`, except that the code is evaluated
            after the chart, available as ``window.chart``, is created.

        Notes
        -----
        Passing ``{ series: [{ data: some_data }] }``, if ``some_data`` is
        a numpy array, it is **more efficient** to leave it as numpy array
        instead of converting it ``some_data.tolist()``, which is done
        implicitly.
        """
        options = (options or {}).copy()
        if not isinstance(options, MutableMapping):
            raise ValueError('options must be dict')

        if kwargs:
            _merge_dicts(options, _kwargs_options(kwargs))
        self.exposeObject('pydata', options)
        highchart = highchart or self.highchart or 'Chart'
        self._evalJS('''
            {javascript};
            window.chart = new Highcharts.{highchart}(pydata);
            {javascript_after};
        '''.format(**locals()))

    _ENSURE_HAVE = '''
    (function(){
        var __check = setInterval(function() {
            if (%s) { clearInterval(__check); %%s; }
        }, 10);
    })();
    '''
    _ENSURE_HAVE_HIGHCHARTS = _ENSURE_HAVE % 'window.jQuery && window.Highcharts'
    _ENSURE_HAVE_CHART = _ENSURE_HAVE % 'window.Highcharts && window.chart'

    def _evalJS(self, javascript):
        super().evalJS(self._ENSURE_HAVE_HIGHCHARTS % javascript)

    def evalJS(self, javascript):
        """ Asynchronously evaluate JavaScript code. """
        super().evalJS(self._ENSURE_HAVE_CHART % javascript)

    def clear(self):
        """Remove all series from the chart"""
        self.evalJS('''
        while(chart.series.length > 0) {
            chart.series[0].remove(false);
        }
        chart.redraw();
        ''')

    @pyqtSlot('QVariantList')
    def _on_selected_points(self, points):
        self._selection_callback([np.sort(selected).astype(int)
                                  for selected in points])


if __name__ == '__main__':
    from PyQt4.QtGui import QApplication
    from PyQt4.QtCore import QTimer, pyqtProperty, QObject
    import numpy as np
    app = QApplication([])


    class Bridge(QObject):
        def on_selected_points(self, points):
            print(len(points), points)

    bridge = Bridge()

    w = Highchart(None, bridge, enable_zoom=True, enable_select='xy+',
                  selection_callback=bridge.on_selected_points,
                  debug=True)
    QTimer.singleShot(
        1000, lambda: w.chart(dict(series=[dict(data=np.random.random((100, 2)),
                                               marker=dict(),
                                               )]),
                             # credits_text='BTYB Yours Truly',
                             title_text='Foo plot',
                             chart_type='scatter',

                             ))
    w.show()
    app.exec()

