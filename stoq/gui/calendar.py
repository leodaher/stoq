# -*- Mode: Python; coding: iso-8859-1 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2011 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s): Stoq Team <stoq-devel@async.com.br>
##
"""
stoq/gui/calendar.py:

    Calendar application.
"""

import datetime
import gettext
import json

from kiwi.environ import environ
import gtk
import webkit

from stoqlib.api import api
from stoqlib.domain.payment.payment import Payment
from stoqlib.domain.payment.views import InPaymentView
from stoqlib.domain.payment.views import OutPaymentView
from stoqlib.gui.base.dialogs import run_dialog
from stoqlib.gui.editors.paymenteditor import InPaymentEditor
from stoqlib.lib import dateconstants
from stoqlib.lib.daemonutils import start_daemon

from stoq.gui.application import AppWindow


_ = gettext.gettext


class CalendarView(gtk.ScrolledWindow):
    def __init__(self, app):
        self.app = app
        gtk.ScrolledWindow.__init__(self)
        self.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        self._view = webkit.WebView()
        self._view.props.settings.props.enable_developer_extras = True

        self._view.get_web_inspector().connect(
            'inspect-web-view',
            self._on_inspector__inspect_web_view)
        self._view.connect(
            'navigation-policy-decision-requested',
            self._on_view__navigation_policy_decision_requested)
        self._view.connect(
            'load-finished',
            self._on_view__document_load_finished)
        self.add(self._view)
        self._view.show()

    def _on_inspector__inspect_web_view(self, inspector, view):
        w = gtk.Window()
        w.set_size_request(800, 600)
        sw = gtk.ScrolledWindow()
        w.add(sw)
        view = webkit.WebView()
        sw.add(view)
        w.show_all()
        return view

    def _on_view__document_load_finished(self, view, frame):
        self._load_finished()

    def _on_view__navigation_policy_decision_requested(self, view, frame,
                                                       request, action,
                                                       policy):
        uri = request.props.uri
        if uri.startswith('file:///'):
            policy.use()
        elif uri.startswith('http://localhost'):
            policy.use()
        elif uri.startswith('dialog://'):
            policy.ignore()
            data = uri[9:]
            doc, args = data.split('?', 1)
            kwargs = {}
            for arg in args.split(','):
                k, v = arg.split('=', 1)
                kwargs[k] = v
            self._run_dialog(doc, **kwargs)
        else:
            gtk.show_uri(self.get_screen(), uri,
                         gtk.get_current_event_time())

    def _run_dialog(self, name, **kwargs):
        if name == 'payment':
            self._show_payment_details(**kwargs)
        elif name == 'in-payment-list':
            self._show_in_payment_list(**kwargs)
        elif name == 'out-payment-list':
            self._show_out_payment_list(**kwargs)
        else:
            raise NotImplementedError(name)

    def _show_payment_details(self, id):
        trans = api.new_transaction()
        payment = trans.get(Payment.get(int(id)))
        retval = run_dialog(InPaymentEditor, self.app, trans, payment)
        if api.finish_transaction(trans, retval):
            self.search.refresh()
        trans.close()

    def _show_in_payment_list(self, ids):
        ids = map(int, ids.split('|'))
        app = self.app.app.launcher.run_app_by_name('receivable')
        app.main_window.select_payment_ids(ids)

    def _show_out_payment_list(self, date):
        y, m, d = map(int, date.split('-'))
        date = datetime.date(y, m, d)
        app = self.app.app.launcher.run_app_by_name('payable')
        app.main_window.search_for_date(date)

    def _load_finished(self):
        self._startup()

    def _startup(self):
        d = {}
        d['monthNames'] = dateconstants.get_month_names()
        d['monthNamesShort'] = dateconstants.get_short_month_names()
        d['dayNames'] = dateconstants.get_day_names()
        d['dayNamesShort'] = dateconstants.get_short_day_names()
        d['buttonText'] = {"today": _('today'),
                           "month": _('month'),
                           "week": _('week'),
                           "day": _('day')}
        s = "startup(%s);" % (json.dumps(d), )
        self._view.execute_script(s)

    def _render_event(self, args):
        self._view.execute_script(
            "$('#calendar').fullCalendar('renderEvent', %s, true);" % (
            json.dumps(args)))

    def print_(self):
        self._view.execute_script('window.print()')

    def _load_daemon_path(self, path):
        uri = '%s/%s' % (self._daemon_uri, path)
        self._view.load_uri(uri)

    def set_daemon_uri(self, uri):
        self._daemon_uri = uri

    def load(self):
        self._load_daemon_path('web/static/calendar-app.html')

class CalendarApp(AppWindow):

    app_name = _('Calendar')
    app_icon_name = 'stoq-calendar-app'
    gladefile = 'calendar'
    embedded = True

    def __init__(self, app):
        AppWindow.__init__(self, app)
        self._setup_daemon()

    @api.async
    def _setup_daemon(self):
        daemon = yield start_daemon()
        self._calendar.set_daemon_uri(daemon.base_uri)

        proxy = daemon.get_client()
        service = yield proxy.callRemote('start_webservice')
        self._calendar.load()

    #
    # AppWindow overrides
    #

    def create_actions(self):
        actions = [
            ('Print', gtk.STOCK_PRINT, _("Print..."),
             None, _('Print a transaction report')),
            ('ExportCSV', None, _('Export CSV...'), '<control>F10'),
            ("NewTask", gtk.STOCK_NEW, _("Task..."), '<control>t',
             _("Add a new task")),
            ]
        self.calendar_ui = self.add_ui_actions('', actions,
                                                filename='calendar.xml')
        self.help_ui = None

    def create_ui(self):
        self._calendar = CalendarView(self)
        self.main_vbox.pack_start(self._calendar)
        self._calendar.show()
        self.app.launcher.add_new_items([self.NewTask])

    def activate(self):
        self.app.launcher.SearchToolItem.set_sensitive(False)

    def deactivate(self):
        self.uimanager.remove_ui(self.calendar_ui)
        self.app.launcher.SearchToolItem.set_sensitive(True)

    #
    # Kiwi callbacks
    #

    # Toolbar

    def new_activate(self):
        pass

    # Calendar

    def on_Print__activate(self, action):
        self._calendar.print_()

    def on_ExportCSV__activate(self, action):
        pass
