# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa virtual hardware /dev/ package."""

from aura.hardware.device_manager import DeviceManager, DeviceDescriptor
from aura.hardware.vcpu import VCPUDevice
from aura.hardware.vram import VRAMDevice
from aura.hardware.vdisk import VDiskDevice
from aura.hardware.vnet import VNetDevice
from aura.hardware.vbt import VBTDevice
from aura.hardware.vgpu import VGPUDevice

__all__ = [
    "DeviceManager",
    "DeviceDescriptor",
    "VCPUDevice",
    "VRAMDevice",
    "VDiskDevice",
    "VNetDevice",
    "VBTDevice",
    "VGPUDevice",
]
