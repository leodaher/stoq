# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2009 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
##
## You should have received a copy of the GNU Lesser General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s): Stoq Team <stoq-devel@async.com.br>
##
""" Base classes to manage production informations """

import datetime
from decimal import Decimal

from zope.interface import implements

from stoqlib.database.orm import (UnicodeCol, ForeignKey, DateTimeCol, IntCol,
                                  QuantityCol)
from stoqlib.domain.base import Domain
from stoqlib.domain.product import ProductHistory
from stoqlib.domain.interfaces import IContainer, IDescribable, IStorable
from stoqlib.lib.translation import stoqlib_gettext

_ = stoqlib_gettext


class ProductionOrder(Domain):
    """Production Order object implementation.

    @cvar ORDER_OPENED: The production order is opened, production items might
                        have been added.
    @cvar ORDER_WAITING: The production order is waiting some conditions to
                         start the manufacturing process.
    @cvar ORDER_PRODUCTION: The production order have already started.
    @cvar ORDER_CLOSED: The production have finished.

    @ivar status: the production order status
    @ivar open_date: the date when the production order was created
    @ivar close_date: the date when the production order have been closed
    @ivar description: the production order description
    @ivar responsible: the person responsible for the production order
    """
    implements(IContainer, IDescribable)

    (ORDER_OPENED,
     ORDER_WAITING,
     ORDER_PRODUCING,
     ORDER_CLOSED) = range(4)

    statuses = {ORDER_OPENED:         _(u'Opened'),
                ORDER_WAITING:        _(u'Waiting'),
                ORDER_PRODUCING:      _(u'Producing'),
                ORDER_CLOSED:         _(u'Closed')}

    status = IntCol(default=ORDER_OPENED)
    open_date = DateTimeCol(default=datetime.datetime.now)
    expected_start_date = DateTimeCol(default=None)
    start_date = DateTimeCol(default=None)
    close_date = DateTimeCol(default=None)
    description = UnicodeCol(default='')
    responsible = ForeignKey('PersonAdaptToEmployee', default=None)
    branch = ForeignKey('PersonAdaptToBranch')

    #
    # IContainer implmentation
    #

    def get_items(self):
        return ProductionItem.selectBy(order=self,
                                       connection=self.get_connection())

    def add_item(self, sellable, quantity=Decimal(1)):
        return ProductionItem(order=self, product=sellable.product,
                              quantity=quantity,
                              connection=self.get_connection())

    def remove_item(self, item):
        assert isinstance(item, ProductionItem)
        if item.order is not self:
            raise ValueError(_('Argument item must have an order attribute '
                               'associated with the current production '
                               'order instance.'))
        ProductionItem.delete(item.id, connection=self.get_connection())

    #
    # Public API
    #

    def get_service_items(self):
        """Returns all the services needed by this production.

        @returns: a sequence of L{ProductionService} instances.
        """
        return ProductionService.selectBy(order=self,
                                          connection=self.get_connection())

    def remove_service_item(self, item):
        assert isinstance(item, ProductionService)
        if item.order is not self:
            raise ValueError(_('Argument item must have an order attribute '
                               'associated with the current production '
                               'order instance.'))
        ProductionService.delete(item.id, connection=self.get_connection())

    def get_material_items(self):
        """Returns all the material needed by this production.

        @returns: a sequence of L{ProductionMaterial} instances.
        """
        return ProductionMaterial.selectBy(order=self,
                                           connection=self.get_connection())

    def start_production(self):
        """Start the production by allocating all the material needed.
        """
        assert self.status in [ProductionOrder.ORDER_OPENED,
                               ProductionOrder.ORDER_WAITING]

        for material in self.get_material_items():
            material.allocate()

        self.start_date = datetime.date.today()
        self.status = ProductionOrder.ORDER_PRODUCING

    def try_finalize_production(self):
        """When all items are completely produced, change the status of the
        production to CLOSED.
        """
        assert self.status == ProductionOrder.ORDER_PRODUCING

        # All items must be completely produced.
        if all([i.is_completely_produced() for i in self.get_items()]):
            self.close_date = datetime.date.today()
            self.status = ProductionOrder.ORDER_CLOSED

    def set_production_waiting(self):
        assert self.status == ProductionOrder.ORDER_OPENED

        self.status = ProductionOrder.ORDER_WAITING

    def get_status_string(self):
        return ProductionOrder.statuses[self.status]

    def get_order_number(self):
        return u'%04d' % self.id

    def get_branch_name(self):
        return self.branch.person.name

    def get_responsible_name(self):
        if self.responsible is not None:
            return self.responsible.person.name
        return u''

    #
    # IDescribable implementation
    #

    def get_description(self):
        return self.description


class ProductionItem(Domain):
    """Production Item object implementation.

    @ivar order: The L{ProductionOrder} of this item.
    @ivar product: The product that will be manufactured.
    @ivar quantity: The product's quantity that will be manufactured.
    @ivar produced: The product's quantity that was manufactured.
    @ivar lost: The product's quantity that was lost.
    """
    implements(IDescribable)

    quantity = QuantityCol(default=1)
    produced = QuantityCol(default=0)
    lost = QuantityCol(default=0)
    order = ForeignKey('ProductionOrder')
    product = ForeignKey('Product')

    #
    # IDescribable Implementation
    #

    def get_description(self):
        return self.product.sellable.get_description()

    #
    # Private API
    #

    def _get_material_from_component(self, component):
        return ProductionMaterial.selectOneBy(product=component.component,
                                              order=self.order,
                                              connection=self.get_connection())

    #
    # Public API
    #

    def get_unit_description(self):
        return self.product.sellable.get_unit_description()

    def get_components(self):
        return self.product.get_components()

    def can_produce(self, quantity):
        """Returns if we can produce a certain quantity.  We can produce a
        quantity items until we reach the total quantity that will be
        manufactured minus the quantity that was lost.

        @param quantity: the quantity that will be produced.
        """
        assert quantity > 0

        return self.produced + quantity + self.lost <= self.quantity

    def is_completely_produced(self):
        return self.quantity == self.produced + self.lost

    def produce(self, quantity):
        """Sets a certain quantity as produced. The quantity will be marked as
        produced only if there are enough materials allocated, otherwise a
        ValueError exception will be raised.

        @param quantity: the quantity that will be produced.
        """
        assert self.can_produce(quantity)

        conn = self.get_connection()
        conn.savepoint('before_produce')

        for component in self.get_components():
            material = self._get_material_from_component(component)
            needed_material = quantity * component.quantity

            try:
                material.consume(needed_material)
            except ValueError:
                conn.rollback_to_savepoint('before_produce')
                raise

        storable = IStorable(self.product, None)
        storable.increase_stock(quantity, self.order.branch)
        self.produced += quantity
        self.order.try_finalize_production()
        ProductHistory.add_produced_item(conn, self.order.branch, self)

    def add_lost(self, quantity):
        """Adds a quantity that was lost. The maximum quantity that can be
        lost is the total quantity minus the quantity already produced.

        @param quantity: the quantity that was lost.
        """
        if self.lost + quantity > self.quantity - self.produced:
            raise ValueError(
                _('Can not lost more items than the total production quantity.'))

        conn = self.get_connection()
        conn.savepoint('before_lose')

        for component in self.get_components():
            material = self._get_material_from_component(component)
            try:
                material.add_lost(quantity * component.quantity)
            except ValueError:
                conn.rollback_to_savepoint('before_lose')
                raise

        self.lost += quantity
        self.order.try_finalize_production()
        ProductHistory.add_lost_item(conn, self.order.branch, self)


class ProductionMaterial(Domain):
    """Production Material object implementation.

    @ivar order: The L{ProductionOrder} that will consume this material.
    @ivar product: The product that will be consumed.
    @ivar needed: The quantity needed of this material.
    @ivar consumed: The quantity already used of this material.
    @ivar lost: The quantity lost of this material.
    @ivar to_purchase: The quantity to purchase of this material.
    @ivar to_make: The quantity to manufacture of this material.
    """
    implements(IDescribable)

    needed = QuantityCol(default=1)
    allocated = QuantityCol(default=0)
    consumed = QuantityCol(default=0)
    lost = QuantityCol(default=0)
    to_purchase = QuantityCol(default=0)
    to_make = QuantityCol(default=0)
    order = ForeignKey('ProductionOrder')
    product = ForeignKey('Product')

    #
    # Public API
    #

    def allocate(self, quantity=None):
        """Allocates the needed quantity of this material by decreasing the
        stock quantity. If no quantity was specified, it will decrease all the
        stock needed or the maximum quantity available. Otherwise, allocate the
        quantity specified or raise a ValueError exception, if the quantity is
        not available.

        @param quantity: the quantity to be allocated or None to allocate the
                         maximum quantity possible.
        """
        stock = self.get_stock_quantity()
        storable = IStorable(self.product, None)
        assert storable is not None

        if quantity is None:
            required = self.needed - self.allocated
            if stock > required:
                quantity = required
            else:
                quantity = stock
        elif quantity > stock:
            raise ValueError(_('Can not allocate this quantity.'))

        if quantity > 0:
            self.allocated += quantity
            storable.decrease_stock(quantity, self.order.branch)

    def add_lost(self, quantity):
        """Adds the quantity lost of this material. The maximum quantity that
        can be lost is given by the formula:
            - max_lost(quantity) = needed - consumed - lost - quantity

        @param quantity: the quantity that was lost.
        """
        assert quantity > 0

        if self.lost + quantity > self.needed - self.consumed:
            raise ValueError(_('Cannot loose this quantity.'))

        required = self.consumed + self.lost + quantity
        if required > self.allocated:
            self.allocate(required - self.allocated)

        self.lost += quantity
        conn = self.get_connection()
        ProductHistory.add_lost_item(conn, self.order.branch, self)

    def consume(self, quantity):
        """Consumes a certain quantity of material. The maximum quantity
        allowed to be consumed is given by the following formula:
            - max_consumed(quantity) = needed - consumed - lost - quantity

        @param quantity: the quantity to be consumed.
        """
        assert quantity > 0

        if self.consumed + quantity > self.needed - self.lost:
            raise ValueError(_('Can not consume this quantity.'))

        required = self.consumed + self.lost + quantity
        if required > self.allocated:
            self.allocate(required - self.allocated)

        self.consumed += quantity
        conn = self.get_connection()
        ProductHistory.add_consumed_item(conn, self.order.branch, self)

    #
    # IDescribable Implementation
    #

    def get_description(self):
        return self.product.sellable.get_description()

    # Accessors

    def get_unit_description(self):
        return self.product.sellable.get_unit_description()

    def get_stock_quantity(self):
        storable = IStorable(self.product, None)
        assert storable is not None
        return storable.get_full_balance(self.order.branch)


class ProductionService(Domain):
    """Production Service object implementation.

    @ivar order: The L{ProductionOrder} of this service.
    @ivar service: The service that will be used by the production.
    @ivar quantity: The service's quantity.
    """
    implements(IDescribable)

    quantity = QuantityCol(default=1)
    order = ForeignKey('ProductionOrder')
    service = ForeignKey('Service')

    #
    # IDescribable Implementation
    #

    def get_description(self):
        return self.service.sellable.get_description()

    # Accessors

    def get_unit_description(self):
        return self.service.sellable.get_unit_description()
