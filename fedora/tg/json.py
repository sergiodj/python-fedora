# -*- coding: utf-8 -*-
#
# Copyright © 2007-2008  Red Hat, Inc. All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.  You should have
# received a copy of the GNU General Public License along with this program;
# if not, write to the Free Software Foundation, Inc., 51 Franklin Street,
# Fifth Floor, Boston, MA 02110-1301, USA. Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#
# Red Hat Author(s): Toshio Kuratomi <tkuratom@redhat.com>
#

'''
JSON Helper functions.  Most JSON code directly related to classes is
implemented via the __json__() methods in model.py.  These methods define
methods of transforming a class into json for a few common types.
'''
# A JSON-based API(view) for your app.
# Most rules would look like:
# @jsonify.when("isinstance(obj, YourClass)")
# def jsonify_yourclass(obj):
#     return [obj.val1, obj.val2]
# @jsonify can convert your objects to following types:
# lists, dicts, numbers and strings

import warnings
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.ext.associationproxy
import sqlalchemy.engine.base
from turbojson.jsonify import jsonify

from fedora import _

class SABase(object):
    '''Base class for SQLAlchemy mapped objects.

    This base class makes sure we have a __json__() method on each SQLAlchemy
    mapped object that knows how to::

    1) return json for the object.
    2) Can selectively add tables pulled in from the table to the data we're
       returning.
    '''
    # pylint: disable-msg=R0903
    def __json__(self):
        '''Transform any SA mapped class into json.

        This method takes an SA mapped class and turns the "normal" python
        attributes into json.  The properties (from properties in the mapper)
        are also included if they have an entry in json_props.  You make
        use of this by setting json_props in the controller.

        Example controller::
          john = model.Person.get_by(name='John')
          # Person has a property, addresses, linking it to an Address class.
          # Address has a property, phone_nums, linking it to a Phone class.
          john.json_props = {'Person': ['addresses'],
                  'Address': ['phone_nums']}
          return dict(person=john)

        json_props is a dict that maps class names to lists of properties you
        want to output.  This allows you to selectively pick properties you
        are interested in for one class but not another.  You are responsible
        for avoiding loops.  ie: *don't* do this::
            john.json_props = {'Person': ['addresses'], 'Address': ['people']}
        '''
        props = {}
        # pylint: disable-msg=E1101
        if hasattr(self, 'json_props') \
                and self.json_props.has_key(self.__class__.__name__):
            prop_list = self.json_props[self.__class__.__name__]
        elif hasattr(self, 'jsonProps') \
                and self.jsonProps.has_key(self.__class__.__name__):
            # jsonProps is deprecated.
            warnings.warn(_('jsonProps has been renamed to json_props.'
                '  jsonProps will disappear in 0.4'), DeprecationWarning,
                stacklevel=2)
            prop_list = self.jsonProps[self.__class__.__name__]
        else:
            prop_list = {}
        # pylint: enable-msg=E1101

        # Load all the columns from the table
        for column in sqlalchemy.orm.object_mapper(self).iterate_properties:
            if isinstance(column, sqlalchemy.orm.properties.ColumnProperty):
                props[column.key] = getattr(self, column.key)

        # Load things that are explicitly listed
        for field in prop_list:
            props[field] = getattr(self, field)
            try:
                # pylint: disable-msg=E1101
                props[field].json_props = self.json_props
            except AttributeError: # pylint: disable-msg=W0704
                # Certain types of objects are terminal and won't allow setting
                # json_props
                pass

            # Note: Because of the architecture of simplejson and turbojson,
            # anything that inherits from a builtin list, tuple, basestring,
            # or dict but needs special handling needs to be specified
            # expicitly here.  Using the @jsonify.when() decorator won't work.
            if isinstance(props[field],
                    sqlalchemy.orm.collections.InstrumentedList):
                props[field] = jsonify_salist(props[field])

        return props

@jsonify.when("isinstance(obj, sqlalchemy.orm.query.Query)")
def jsonify_sa_select_results(obj):
    '''Transform selectresults into lists.

    The one special thing is that we bind the special json_props into each
    descendent.  This allows us to specify a json_props on the toplevel
    query result and it will pass to all of its children.
    '''
    if 'json_props' in obj.__dict__:
        for element in obj:
            element.json_props = obj.json_props
    elif 'jsonProps' in obj.__dict__:
        warnings.warn(_('jsonProps has been renamed to json_props.  jsonProps'
                ' will disappear in 0.4'), DeprecationWarning, stacklevel=2)
        for element in obj:
            element.json_props = obj.jsonProps
    return list(obj)

# Note: due to the way simplejson works, InstrumentedList has to be taken care
# of explicitly in SABase's __json__() method.  (This is true of any object
# derived from a builtin type (list, dict, tuple, etc))
@jsonify.when('''(
        isinstance(obj, sqlalchemy.orm.collections.InstrumentedList) or
        isinstance(obj, sqlalchemy.orm.attributes.InstrumentedAttribute) or
        isinstance(obj, sqlalchemy.ext.associationproxy._AssociationList))''')
def jsonify_salist(obj):
    '''Transform SQLAlchemy InstrumentedLists into json.

    The one special thing is that we bind the special json_props into each
    descendent.  This allows us to specify a json_props on the toplevel
    query result and it will pass to all of its children.
    '''
    if 'json_props' in obj.__dict__:
        for element in obj:
            element.json_props = obj.json_props
    elif 'jsonProps' in obj.__dict__:
        warnings.warn(_('jsonProps has been renamed to json_props.  jsonProps'
                ' will disappear in 0.4'), DeprecationWarning, stacklevel=2)
        for element in obj:
            element.json_props = obj.jsonProps
    return [jsonify(element) for element in  obj]

@jsonify.when('''(
        isinstance(obj, sqlalchemy.engine.base.ResultProxy)
        )''')
def jsonify_saresult(obj):
    '''Transform SQLAlchemy ResultProxy into json.

    The one special thing is that we bind the special json_props into each
    descendent.  This allows us to specify a json_props on the toplevel
    query result and it will pass to all of its children.
    '''
    if 'json_props' in obj.__dict__:
        for element in obj:
            element.json_props = obj.json_props
    elif 'jsonProps' in obj.__dict__:
        warnings.warn(_('jsonProps has been renamed to json_props.  jsonProps'
                ' will disappear in 0.4'), DeprecationWarning, stacklevel=2)
        for element in obj:
            element.json_props = obj.jsonProps
    return [list(row) for row in obj]

@jsonify.when('''(isinstance(obj, set))''')
def jsonify_set(obj):
    '''Transform a set into a list.'''
    return list(obj)
