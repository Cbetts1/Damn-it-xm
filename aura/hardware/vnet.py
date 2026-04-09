# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa /dev/vnet — Virtual Network Device
=========================================
The /dev/vnet device is the unified virtual network stack.

This module re-exports :class:`~aura.network.stack.NetworkStack` as the
``VNetDevice`` device class, matching the /dev/ device naming convention.
"""

from aura.network.stack import NetworkStack as VNetDevice

__all__ = ["VNetDevice"]
