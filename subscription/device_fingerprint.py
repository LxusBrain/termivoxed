"""
Device Fingerprinting System for TermiVoxed

Generates a unique, stable device fingerprint from hardware identifiers.
This is similar to how Adobe Creative Cloud, Spotify, and Netflix identify devices.

The fingerprint is:
- Unique per physical device
- Stable across app reinstalls
- Extremely difficult to spoof
- Privacy-preserving (one-way hash)
"""

import hashlib
import platform
import subprocess
import re
import sys
import os
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# App-specific salt to prevent cross-application fingerprint reuse
# Use environment variable for security, with fallback for development
def _get_app_salt() -> str:
    """
    Get the application salt from environment variable.

    In production, set TERMIVOXED_FINGERPRINT_SALT environment variable.
    Falls back to a default for development (not recommended for production).
    """
    import os

    env_salt = os.environ.get("TERMIVOXED_FINGERPRINT_SALT")

    if env_salt:
        return env_salt

    # Development fallback - log warning
    if os.environ.get("TERMIVOXED_ENV") == "production":
        logger.warning(
            "SECURITY WARNING: TERMIVOXED_FINGERPRINT_SALT not set in production! "
            "Set this environment variable for secure fingerprinting."
        )

    return "TERMIVOXED_DEV_SALT_CHANGE_IN_PRODUCTION"


APP_SALT = _get_app_salt()


@dataclass
class DeviceInfo:
    """Device information for display purposes"""
    device_name: str
    device_type: str  # WINDOWS, MACOS, LINUX
    os_version: str
    hostname: str
    fingerprint: str
    created_at: datetime


class DeviceFingerprint:
    """
    Generate a unique device fingerprint from hardware identifiers.

    The fingerprint combines multiple hardware identifiers to create a stable,
    unique identifier that:
    - Survives OS reinstalls (based on hardware, not software)
    - Cannot be easily spoofed without hardware changes
    - Is consistent across app reinstalls
    """

    # Cache the fingerprint to avoid repeated system calls
    _cached_fingerprint: Optional[str] = None
    _cached_device_info: Optional[DeviceInfo] = None

    @classmethod
    def generate(cls) -> str:
        """
        Generate or return cached device fingerprint.

        Returns:
            32-character hexadecimal fingerprint string
        """
        if cls._cached_fingerprint:
            return cls._cached_fingerprint

        system = platform.system().lower()

        if system == "windows":
            fingerprint = cls._generate_windows()
        elif system == "darwin":
            fingerprint = cls._generate_macos()
        elif system == "linux":
            fingerprint = cls._generate_linux()
        else:
            # Fallback for unknown systems
            fingerprint = cls._generate_fallback()

        cls._cached_fingerprint = fingerprint
        return fingerprint

    @classmethod
    def get_device_info(cls) -> DeviceInfo:
        """
        Get device information for display purposes.

        Returns:
            DeviceInfo dataclass with device details
        """
        if cls._cached_device_info:
            return cls._cached_device_info

        system = platform.system()

        cls._cached_device_info = DeviceInfo(
            device_name=cls._get_device_name(),
            device_type=system.upper() if system in ["Windows", "Darwin", "Linux"] else "UNKNOWN",
            os_version=platform.platform(),
            hostname=platform.node(),
            fingerprint=cls.generate(),
            created_at=datetime.utcnow()
        )

        return cls._cached_device_info

    @classmethod
    def _get_device_name(cls) -> str:
        """Get a human-readable device name"""
        system = platform.system()

        if system == "Darwin":
            try:
                result = subprocess.run(
                    ["scutil", "--get", "ComputerName"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass

        # Fallback to hostname
        hostname = platform.node()
        if hostname:
            return hostname

        return f"{system} Device"

    @classmethod
    def _generate_windows(cls) -> str:
        """Generate fingerprint for Windows systems"""
        components = []

        # 1. Machine GUID (unique per Windows installation, persists across reinstalls)
        machine_guid = cls._windows_registry_read(
            r"SOFTWARE\Microsoft\Cryptography",
            "MachineGuid"
        )
        if machine_guid:
            components.append(("machine_guid", machine_guid))

        # 2. BIOS Serial Number
        bios_serial = cls._windows_wmi_query(
            "SELECT SerialNumber FROM Win32_BIOS"
        )
        if bios_serial:
            components.append(("bios_serial", bios_serial))

        # 3. Motherboard Serial Number
        board_serial = cls._windows_wmi_query(
            "SELECT SerialNumber FROM Win32_BaseBoard"
        )
        if board_serial:
            components.append(("board_serial", board_serial))

        # 4. Primary Disk Serial
        disk_serial = cls._windows_wmi_query(
            "SELECT SerialNumber FROM Win32_DiskDrive WHERE Index=0"
        )
        if disk_serial:
            components.append(("disk_serial", disk_serial))

        # 5. CPU Processor ID
        cpu_id = cls._windows_wmi_query(
            "SELECT ProcessorId FROM Win32_Processor"
        )
        if cpu_id:
            components.append(("cpu_id", cpu_id))

        # 6. Product ID
        product_id = cls._windows_registry_read(
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            "ProductId"
        )
        if product_id:
            components.append(("product_id", product_id))

        # 7. Primary MAC Address
        mac_address = cls._get_primary_mac()
        if mac_address:
            components.append(("mac_address", mac_address))

        return cls._hash_components(components)

    @classmethod
    def _generate_macos(cls) -> str:
        """Generate fingerprint for macOS systems"""
        components = []

        # 1. Hardware UUID (unique per Mac, persists across OS reinstalls)
        hardware_uuid = cls._macos_get_hardware_uuid()
        if hardware_uuid:
            components.append(("hardware_uuid", hardware_uuid))

        # 2. Serial Number
        serial_number = cls._macos_get_serial_number()
        if serial_number:
            components.append(("serial_number", serial_number))

        # 3. MAC Address of primary interface
        mac_address = cls._macos_get_mac_address()
        if mac_address:
            components.append(("mac_address", mac_address))

        # 4. Model Identifier
        model_id = cls._macos_get_model_identifier()
        if model_id:
            components.append(("model_id", model_id))

        # 5. Boot ROM Version (rarely changes)
        boot_rom = cls._macos_get_boot_rom()
        if boot_rom:
            components.append(("boot_rom", boot_rom))

        return cls._hash_components(components)

    @classmethod
    def _generate_linux(cls) -> str:
        """Generate fingerprint for Linux systems"""
        components = []

        # 1. Machine ID (systemd-based, stable across reboots)
        machine_id = cls._linux_read_file("/etc/machine-id")
        if machine_id:
            components.append(("machine_id", machine_id))

        # 2. Product UUID (DMI/SMBIOS)
        product_uuid = cls._linux_read_dmi("product_uuid")
        if product_uuid:
            components.append(("product_uuid", product_uuid))

        # 3. Board Serial
        board_serial = cls._linux_read_dmi("board_serial")
        if board_serial:
            components.append(("board_serial", board_serial))

        # 4. Product Serial
        product_serial = cls._linux_read_dmi("product_serial")
        if product_serial:
            components.append(("product_serial", product_serial))

        # 5. Primary disk serial
        disk_serial = cls._linux_get_disk_serial()
        if disk_serial:
            components.append(("disk_serial", disk_serial))

        # 6. MAC Address
        mac_address = cls._get_primary_mac()
        if mac_address:
            components.append(("mac_address", mac_address))

        # 7. CPU ID if available
        cpu_id = cls._linux_get_cpu_id()
        if cpu_id:
            components.append(("cpu_id", cpu_id))

        return cls._hash_components(components)

    @classmethod
    def _generate_fallback(cls) -> str:
        """Fallback fingerprint generation for unknown systems"""
        components = []

        # Use available cross-platform identifiers
        mac_address = cls._get_primary_mac()
        if mac_address:
            components.append(("mac_address", mac_address))

        # Hostname (less stable but better than nothing)
        hostname = platform.node()
        if hostname:
            components.append(("hostname", hostname))

        # Platform info
        platform_info = platform.platform()
        if platform_info:
            components.append(("platform", platform_info))

        # UUID based on MAC (as last resort)
        if not components:
            components.append(("uuid", str(uuid.getnode())))

        return cls._hash_components(components)

    # ============ Windows Helper Methods ============

    @classmethod
    def _windows_registry_read(cls, key_path: str, value_name: str) -> Optional[str]:
        """Read a value from Windows Registry"""
        if platform.system() != "Windows":
            return None

        try:
            import winreg

            # Try HKEY_LOCAL_MACHINE first
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                value, _ = winreg.QueryValueEx(key, value_name)
                winreg.CloseKey(key)
                return str(value).strip()
            except WindowsError:
                pass

            # Try HKEY_CURRENT_USER as fallback
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                value, _ = winreg.QueryValueEx(key, value_name)
                winreg.CloseKey(key)
                return str(value).strip()
            except WindowsError:
                pass

        except Exception as e:
            logger.debug(f"Registry read failed for {key_path}\\{value_name}: {e}")

        return None

    @classmethod
    def _windows_wmi_query(cls, query: str) -> Optional[str]:
        """Execute a WMI query and return the first result"""
        if platform.system() != "Windows":
            return None

        try:
            import wmi
            c = wmi.WMI()

            # Parse query to get class and property
            # e.g., "SELECT SerialNumber FROM Win32_BIOS"
            match = re.match(r"SELECT\s+(\w+)\s+FROM\s+(\w+)", query, re.IGNORECASE)
            if not match:
                return None

            property_name = match.group(1)
            class_name = match.group(2)

            for item in getattr(c, class_name)():
                value = getattr(item, property_name, None)
                if value and str(value).strip():
                    return str(value).strip()

        except ImportError:
            # wmi module not available, try PowerShell
            try:
                ps_query = f"Get-CimInstance -Query \"{query}\" | Select-Object -ExpandProperty {property_name}"
                result = subprocess.run(
                    ["powershell", "-Command", ps_query],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception as e:
                logger.debug(f"PowerShell WMI query failed: {e}")

        except Exception as e:
            logger.debug(f"WMI query failed: {query} - {e}")

        return None

    # ============ macOS Helper Methods ============

    @classmethod
    def _macos_system_profiler(cls, data_type: str) -> str:
        """Get output from system_profiler"""
        try:
            result = subprocess.run(
                ["system_profiler", data_type],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            logger.debug(f"system_profiler {data_type} failed: {e}")

        return ""

    @classmethod
    def _macos_get_hardware_uuid(cls) -> Optional[str]:
        """Get Hardware UUID from macOS"""
        output = cls._macos_system_profiler("SPHardwareDataType")

        match = re.search(r"Hardware UUID:\s*([A-F0-9-]+)", output, re.IGNORECASE)
        if match:
            return match.group(1)

        # Alternative: ioreg
        try:
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                timeout=5
            )
            match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', result.stdout)
            if match:
                return match.group(1)
        except Exception:
            pass

        return None

    @classmethod
    def _macos_get_serial_number(cls) -> Optional[str]:
        """Get Serial Number from macOS"""
        output = cls._macos_system_profiler("SPHardwareDataType")

        match = re.search(r"Serial Number \(system\):\s*(\S+)", output)
        if match:
            return match.group(1)

        # Alternative: ioreg
        try:
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                timeout=5
            )
            match = re.search(r'"IOPlatformSerialNumber"\s*=\s*"([^"]+)"', result.stdout)
            if match:
                return match.group(1)
        except Exception:
            pass

        return None

    @classmethod
    def _macos_get_mac_address(cls) -> Optional[str]:
        """Get primary MAC address on macOS"""
        try:
            result = subprocess.run(
                ["ifconfig", "en0"],
                capture_output=True,
                text=True,
                timeout=5
            )
            match = re.search(r"ether\s+([0-9a-f:]+)", result.stdout, re.IGNORECASE)
            if match:
                return match.group(1).upper().replace(":", "")
        except Exception:
            pass

        return cls._get_primary_mac()

    @classmethod
    def _macos_get_model_identifier(cls) -> Optional[str]:
        """Get Model Identifier from macOS"""
        output = cls._macos_system_profiler("SPHardwareDataType")

        match = re.search(r"Model Identifier:\s*(\S+)", output)
        if match:
            return match.group(1)

        return None

    @classmethod
    def _macos_get_boot_rom(cls) -> Optional[str]:
        """Get Boot ROM Version from macOS"""
        output = cls._macos_system_profiler("SPHardwareDataType")

        match = re.search(r"Boot ROM Version:\s*(\S+)", output)
        if match:
            return match.group(1)

        return None

    # ============ Linux Helper Methods ============

    @classmethod
    def _linux_read_file(cls, path: str) -> Optional[str]:
        """Read content from a file on Linux"""
        try:
            content = Path(path).read_text().strip()
            if content:
                return content
        except Exception:
            pass

        return None

    @classmethod
    def _linux_read_dmi(cls, name: str) -> Optional[str]:
        """Read DMI/SMBIOS information"""
        paths = [
            f"/sys/class/dmi/id/{name}",
            f"/sys/devices/virtual/dmi/id/{name}",
        ]

        for path in paths:
            value = cls._linux_read_file(path)
            if value and value.lower() not in ["to be filled", "default string", "not specified"]:
                return value

        return None

    @classmethod
    def _linux_get_disk_serial(cls) -> Optional[str]:
        """Get primary disk serial on Linux"""
        try:
            # Try udevadm
            result = subprocess.run(
                ["udevadm", "info", "--query=property", "--name=/dev/sda"],
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.split("\n"):
                if line.startswith("ID_SERIAL="):
                    return line.split("=", 1)[1].strip()

        except Exception:
            pass

        try:
            # Try hdparm as fallback
            result = subprocess.run(
                ["hdparm", "-I", "/dev/sda"],
                capture_output=True,
                text=True,
                timeout=5
            )

            match = re.search(r"Serial Number:\s*(\S+)", result.stdout)
            if match:
                return match.group(1)

        except Exception:
            pass

        return None

    @classmethod
    def _linux_get_cpu_id(cls) -> Optional[str]:
        """Get CPU ID on Linux"""
        try:
            content = Path("/proc/cpuinfo").read_text()

            # Look for Serial (on some ARM/Raspberry Pi)
            match = re.search(r"Serial\s*:\s*(\S+)", content)
            if match:
                return match.group(1)

            # Look for microcode (as a semi-stable identifier)
            match = re.search(r"microcode\s*:\s*(\S+)", content)
            if match:
                return match.group(1)

        except Exception:
            pass

        return None

    # ============ Cross-platform Helper Methods ============

    @classmethod
    def _get_primary_mac(cls) -> Optional[str]:
        """Get primary network interface MAC address"""
        try:
            # uuid.getnode() returns MAC as integer
            mac_int = uuid.getnode()

            # Check if it's a real MAC (not randomly generated)
            # Random MACs have the multicast bit set
            if (mac_int >> 40) & 1:
                return None

            # Format as hex string
            mac_hex = f"{mac_int:012X}"
            return mac_hex

        except Exception:
            pass

        return None

    @classmethod
    def _hash_components(cls, components: List[Tuple[str, str]]) -> str:
        """
        Create a stable hash from components.

        Uses weighted hashing where more stable identifiers have higher weight.
        """
        if not components:
            # Emergency fallback - should never happen
            return hashlib.sha256(f"{APP_SALT}_{uuid.uuid4()}".encode()).hexdigest()[:32]

        # Sort components for consistency
        components.sort(key=lambda x: x[0])

        # Create composite string
        composite = "|".join(f"{name}:{value}" for name, value in components)

        # Add app-specific salt
        salted = f"{APP_SALT}|{composite}"

        # Create SHA-256 hash
        full_hash = hashlib.sha256(salted.encode()).hexdigest()

        # Return first 32 characters (128 bits - sufficient for uniqueness)
        return full_hash[:32]

    @classmethod
    def verify_fingerprint(cls, stored_fingerprint: str) -> bool:
        """
        Verify if the current device matches a stored fingerprint.

        Args:
            stored_fingerprint: Previously stored fingerprint to verify against

        Returns:
            True if fingerprints match, False otherwise
        """
        current = cls.generate()
        return current == stored_fingerprint

    @classmethod
    def get_fingerprint_components(cls) -> Dict[str, str]:
        """
        Get raw fingerprint components for debugging purposes.

        WARNING: This exposes sensitive hardware info. Only use for debugging.
        """
        system = platform.system().lower()
        components = {}

        if system == "windows":
            components["machine_guid"] = cls._windows_registry_read(
                r"SOFTWARE\Microsoft\Cryptography", "MachineGuid"
            ) or "N/A"
            components["bios_serial"] = cls._windows_wmi_query(
                "SELECT SerialNumber FROM Win32_BIOS"
            ) or "N/A"

        elif system == "darwin":
            components["hardware_uuid"] = cls._macos_get_hardware_uuid() or "N/A"
            components["serial_number"] = cls._macos_get_serial_number() or "N/A"

        elif system == "linux":
            components["machine_id"] = cls._linux_read_file("/etc/machine-id") or "N/A"
            components["product_uuid"] = cls._linux_read_dmi("product_uuid") or "N/A"

        components["mac_address"] = cls._get_primary_mac() or "N/A"
        components["hostname"] = platform.node() or "N/A"

        return components

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached fingerprint (useful after hardware changes)"""
        cls._cached_fingerprint = None
        cls._cached_device_info = None


# Convenience functions
def get_device_fingerprint() -> str:
    """Get the device fingerprint (cached)"""
    return DeviceFingerprint.generate()


def get_device_info() -> DeviceInfo:
    """Get device information for display"""
    return DeviceFingerprint.get_device_info()


def verify_device(stored_fingerprint: str) -> bool:
    """Verify if current device matches stored fingerprint"""
    return DeviceFingerprint.verify_fingerprint(stored_fingerprint)


# Self-test when run directly
if __name__ == "__main__":
    print("=" * 60)
    print("Device Fingerprint Generator - TermiVoxed")
    print("=" * 60)
    print()

    fingerprint = get_device_fingerprint()
    device_info = get_device_info()

    print(f"Device Name:    {device_info.device_name}")
    print(f"Device Type:    {device_info.device_type}")
    print(f"OS Version:     {device_info.os_version}")
    print(f"Hostname:       {device_info.hostname}")
    print(f"Fingerprint:    {fingerprint}")
    print()

    print("Raw Components (for debugging):")
    print("-" * 40)
    for key, value in DeviceFingerprint.get_fingerprint_components().items():
        # Mask sensitive values
        masked = value[:4] + "..." + value[-4:] if len(value) > 10 else value
        print(f"  {key}: {masked}")

    print()
    print("Verification Test:")
    print(f"  Fingerprint matches self: {verify_device(fingerprint)}")
    print(f"  Fingerprint matches 'fake': {verify_device('fake123')}")
