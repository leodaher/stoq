# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2013 Async Open Source <http://www.async.com.br>
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

__tests__ = 'stoqlib.gui.wizards.inventorywizard'

from decimal import Decimal

from stoqlib.gui.test.uitestutils import GUITest
from stoqlib.gui.wizards.inventorywizard import (InventoryCountWizard,
                                                 _InventoryBatchSelectionDialog)


class TestInventoryBatchSelectionDialog(GUITest):
    def test_batch_number_validation(self):
        storable = self.create_storable(is_batch=True)
        self.create_storable_batch(storable=storable, batch_number=u'123')

        dialog = _InventoryBatchSelectionDialog(self.store, storable, 10)
        # We cannot use assertValid/assertInvalid here because last entry will
        # change when updating it (the dialog will append another entry that
        # will be the new _last_entry) and those other entriews names on the
        # dialog are set using setattr with a random name
        entry = dialog._last_entry
        entry.update(u'123')
        self.assertTrue(entry.is_valid())
        entry.update(u'124')
        self.assertFalse(entry.is_valid())


class TestInventoryCountWizard(GUITest):
    def test_assisted_count(self):
        product = self.create_product(code='1')
        self.create_storable(product=product)
        inventory = self.create_inventory()
        self.create_inventory_item(inventory=self.create_inventory(), product=product)

        wizard = InventoryCountWizard(self.store, model=inventory)
        type_step = wizard.get_current_step()
        type_step.assisted_count.set_active(True)
        self.click(wizard.next_button)

        count_step = wizard.get_current_step()
        count_step.barcode.update('12')
        self.activate(count_step.barcode)
        # The warning_label should be overlaying the list changing
        overlay = count_step.overlay.get_overlay_pass_through(count_step.box)
        self.assertFalse(overlay)
        self.assertEqual(count_step.warning_label.get_text(), 'Product not found')
        self.assertEqual(count_step.warning_label.get_property('opacity'), Decimal(1))

        # The item is found, the overlay should be off
        count_step.barcode.update('1')
        self.activate(count_step.barcode)
        overlay = count_step.overlay.get_overlay_pass_through(count_step.box)
        self.assertTrue(overlay)
        self.assertEqual(count_step.warning_label.get_property('opacity'), Decimal(0))
