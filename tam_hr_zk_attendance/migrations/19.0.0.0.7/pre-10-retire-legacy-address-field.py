# -*- coding: utf-8 -*-
"""Keep legacy raw-log location columns untouched during upgrade."""


def migrate(cr, version):
    # Older databases use ``address_id`` either as free text or a partner
    # relation. The current module no longer maps that ambiguous column.
    return
