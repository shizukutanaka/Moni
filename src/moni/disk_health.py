"""Advanced disk health monitoring with SMART data, temperature sensors, and predictive analytics."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import psutil
import threading
import re

try:
    import pySMART
    SMART_AVAILABLE = True
except ImportError:
    SMART_AVAILABLE = False


@dataclass
class SmartAttribute:
    """SMART attribute data."""
    id: int
    name: str
    raw_value: int
    normalized_value: int
    threshold: int
    worst: int
    status: str  # OK, WARN, FAIL
    description: str


@dataclass
class DiskHealth:
    """Comprehensive disk health information."""
    device: str
    model: str
    serial: str
    capacity_bytes: int
    interface: str  # SATA, NVMe, USB, etc.
    smart_enabled: bool
    smart_status: str  # PASSED, FAILED, UNKNOWN
    temperature_celsius: Optional[int]
    power_on_hours: Optional[int]
    power_cycle_count: Optional[int]
    total_lbas_written: Optional[int]
    total_lbas_read: Optional[int]
    reallocated_sectors: Optional[int]
    pending_sectors: Optional[int]
    uncorrectable_sectors: Optional[int]
    health_percentage: Optional[int]
    estimated_life_remaining: Optional[int]  # months
    smart_attributes: List[SmartAttribute]
    performance_metrics: Dict[str, float]
    errors: List[str]
    warnings: List[str]


@dataclass
class DiskPerformance:
    """Disk performance metrics."""
    device: str
    read_iops: float
    write_iops: float
    read_throughput_mbps: float
    write_throughput_mbps: float
    read_latency_ms: float
    write_latency_ms: float
    queue_depth: int
    utilization_percent: float
    response_time_ms: float


@dataclass
class FileSystemHealth:
    """File system health and usage information."""
    mount_point: str
    filesystem_type: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    inodes_total: Optional[int]
    inodes_used: Optional[int]
    inodes_free: Optional[int]
    fragmentation_percent: Optional[float]
    last_check: Optional[datetime]
    errors_found: int
    mount_options: List[str]
    device: str


class DiskHealthMonitor:
    """Advanced disk health monitoring and predictive analytics."""

    def __init__(self):
        self.performance_history: Dict[str, List[Dict]] = {}
        self.health_cache: Dict[str, DiskHealth] = {}
        self.last_update = 0
        self.cache_duration = 30  # seconds
        self.critical_smart_attributes = {
            1: "Read Error Rate",
            5: "Reallocated Sectors Count",
            10: "Spin Retry Count",
            196: "Reallocation Event Count",
            197: "Current Pending Sector Count",
            198: "Uncorrectable Sector Count",
            199: "UltraDMA CRC Error Count"
        }

    def get_disk_health_summary(self, force_refresh: bool = False) -> List[DiskHealth]:
        """Get comprehensive disk health information."""
        current_time = time.time()

        if force_refresh or (current_time - self.last_update) > self.cache_duration:
            self._update_disk_health()
            self.last_update = current_time

        return list(self.health_cache.values())

    def _update_disk_health(self):
        """Update disk health information."""
        self.health_cache.clear()

        # Get physical disks
        physical_disks = self._get_physical_disks()

        for disk_info in physical_disks:
            try:
                health = self._analyze_disk_health(disk_info)
                if health:
                    self.health_cache[health.device] = health
            except Exception as e:
                # Create basic health info for disks we can't fully analyze
                health = DiskHealth(
                    device=disk_info.get('device', 'unknown'),
                    model='Unknown',
                    serial='Unknown',
                    capacity_bytes=0,
                    interface='Unknown',
                    smart_enabled=False,
                    smart_status='UNKNOWN',
                    temperature_celsius=None,
                    power_on_hours=None,
                    power_cycle_count=None,
                    total_lbas_written=None,
                    total_lbas_read=None,
                    reallocated_sectors=None,
                    pending_sectors=None,
                    uncorrectable_sectors=None,
                    health_percentage=None,
                    estimated_life_remaining=None,
                    smart_attributes=[],
                    performance_metrics={},
                    errors=[str(e)],
                    warnings=[]
                )
                self.health_cache[health.device] = health

    def _get_physical_disks(self) -> List[Dict[str, Any]]:
        """Get list of physical disk devices."""
        disks = []

        try:
            # Get disk partitions
            partitions = psutil.disk_partitions(all=True)
            seen_devices = set()

            for partition in partitions:
                device = partition.device

                # Extract base device name (remove partition numbers)
                base_device = re.sub(r'\d+$', '', device)
                if base_device in seen_devices:
                    continue

                seen_devices.add(base_device)

                disk_info = {
                    'device': base_device,
                    'partition': device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'opts': partition.opts
                }

                disks.append(disk_info)

            # Add additional physical disks that might not be mounted
            try:
                if SMART_AVAILABLE:
                    smart_disks = pySMART.DeviceList()
                    for device in smart_disks.devices:
                        device_name = getattr(device, 'name', str(device))
                        if device_name not in seen_devices:
                            disks.append({
                                'device': device_name,
                                'partition': device_name,
                                'mountpoint': None,
                                'fstype': None,
                                'opts': None
                            })
            except Exception:
                pass

        except Exception:
            pass

        return disks

    def _analyze_disk_health(self, disk_info: Dict[str, Any]) -> Optional[DiskHealth]:
        """Analyze health of a specific disk."""
        device = disk_info['device']

        # Get SMART data
        smart_data = self._get_smart_data(device)

        # Get basic disk information
        disk_details = self._get_disk_details(device)

        # Get performance metrics
        performance = self._get_performance_metrics(device)

        # Calculate health percentage and life estimation
        health_percentage = self._calculate_health_percentage(smart_data)
        life_remaining = self._estimate_life_remaining(smart_data, performance)

        # Collect warnings and errors
        warnings, errors = self._analyze_smart_warnings(smart_data)

        return DiskHealth(
            device=device,
            model=disk_details.get('model', 'Unknown'),
            serial=disk_details.get('serial', 'Unknown'),
            capacity_bytes=disk_details.get('capacity', 0),
            interface=disk_details.get('interface', 'Unknown'),
            smart_enabled=smart_data.get('enabled', False),
            smart_status=smart_data.get('status', 'UNKNOWN'),
            temperature_celsius=smart_data.get('temperature'),
            power_on_hours=smart_data.get('power_on_hours'),
            power_cycle_count=smart_data.get('power_cycles'),
            total_lbas_written=smart_data.get('lbas_written'),
            total_lbas_read=smart_data.get('lbas_read'),
            reallocated_sectors=smart_data.get('reallocated_sectors'),
            pending_sectors=smart_data.get('pending_sectors'),
            uncorrectable_sectors=smart_data.get('uncorrectable_sectors'),
            health_percentage=health_percentage,
            estimated_life_remaining=life_remaining,
            smart_attributes=smart_data.get('attributes', []),
            performance_metrics=performance,
            errors=errors,
            warnings=warnings
        )

    def _get_smart_data(self, device: str) -> Dict[str, Any]:
        """Get SMART data for a disk device."""
        smart_data = {
            'enabled': False,
            'status': 'UNKNOWN',
            'attributes': [],
            'temperature': None,
            'power_on_hours': None,
            'power_cycles': None,
            'lbas_written': None,
            'lbas_read': None,
            'reallocated_sectors': None,
            'pending_sectors': None,
            'uncorrectable_sectors': None
        }

        try:
            # Try pySMART first
            if SMART_AVAILABLE:
                smart_data.update(self._get_smart_data_pysmart(device))
            else:
                # Fallback to smartctl command
                smart_data.update(self._get_smart_data_smartctl(device))

        except Exception:
            # Try alternative methods
            try:
                smart_data.update(self._get_smart_data_alternative(device))
            except Exception:
                pass

        return smart_data

    def _get_smart_data_pysmart(self, device: str) -> Dict[str, Any]:
        """Get SMART data using pySMART library."""
        data = {}

        try:
            device_obj = pySMART.Device(device)
            if device_obj:
                data['enabled'] = device_obj.smart_enabled
                data['status'] = 'PASSED' if device_obj.smart_status == 'PASSED' else 'FAILED'

                # Get temperature
                if hasattr(device_obj, 'temperature') and device_obj.temperature:
                    data['temperature'] = device_obj.temperature

                # Get attributes
                attributes = []
                if hasattr(device_obj, 'attributes') and device_obj.attributes:
                    for attr in device_obj.attributes:
                        if attr:
                            attribute = SmartAttribute(
                                id=attr.num,
                                name=attr.name,
                                raw_value=attr.raw,
                                normalized_value=attr.value,
                                threshold=attr.thresh,
                                worst=attr.worst,
                                status='OK' if attr.when_failed == '-' else 'FAIL',
                                description=self._get_attribute_description(attr.num)
                            )
                            attributes.append(attribute)

                            # Extract specific values
                            if attr.num == 9:  # Power on hours
                                data['power_on_hours'] = attr.raw
                            elif attr.num == 12:  # Power cycle count
                                data['power_cycles'] = attr.raw
                            elif attr.num == 5:  # Reallocated sectors
                                data['reallocated_sectors'] = attr.raw
                            elif attr.num == 197:  # Current pending sectors
                                data['pending_sectors'] = attr.raw
                            elif attr.num == 198:  # Uncorrectable sectors
                                data['uncorrectable_sectors'] = attr.raw

                data['attributes'] = attributes

        except Exception:
            pass

        return data

    def _get_smart_data_smartctl(self, device: str) -> Dict[str, Any]:
        """Get SMART data using smartctl command."""
        data = {}

        try:
            # Get SMART status
            result = subprocess.run(
                ['smartctl', '-H', device],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode in [0, 4]:  # 0 = OK, 4 = some SMART errors
                output = result.stdout
                if 'SMART overall-health self-assessment test result: PASSED' in output:
                    data['status'] = 'PASSED'
                    data['enabled'] = True
                elif 'SMART overall-health self-assessment test result: FAILED' in output:
                    data['status'] = 'FAILED'
                    data['enabled'] = True

            # Get SMART attributes
            result = subprocess.run(
                ['smartctl', '-A', device],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode in [0, 4]:
                attributes = self._parse_smartctl_attributes(result.stdout)
                data['attributes'] = attributes

                # Extract specific values
                for attr in attributes:
                    if attr.id == 9:  # Power on hours
                        data['power_on_hours'] = attr.raw_value
                    elif attr.id == 12:  # Power cycle count
                        data['power_cycles'] = attr.raw_value
                    elif attr.id == 5:  # Reallocated sectors
                        data['reallocated_sectors'] = attr.raw_value
                    elif attr.id == 197:  # Current pending sectors
                        data['pending_sectors'] = attr.raw_value
                    elif attr.id == 198:  # Uncorrectable sectors
                        data['uncorrectable_sectors'] = attr.raw_value
                    elif attr.id == 194:  # Temperature
                        data['temperature'] = attr.raw_value

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return data

    def _get_smart_data_alternative(self, device: str) -> Dict[str, Any]:
        """Get SMART data using alternative methods."""
        data = {}

        # Try reading from /proc or /sys on Linux
        try:
            import platform
            if platform.system().lower() == 'linux':
                # Try to get temperature from hwmon
                temp = self._get_disk_temperature_linux(device)
                if temp:
                    data['temperature'] = temp

        except Exception:
            pass

        return data

    def _parse_smartctl_attributes(self, output: str) -> List[SmartAttribute]:
        """Parse SMART attributes from smartctl output."""
        attributes = []

        for line in output.split('\n'):
            if line.strip() and line[0].isdigit():
                parts = line.split()
                if len(parts) >= 10:
                    try:
                        attr_id = int(parts[0])
                        attr_name = parts[1]
                        normalized = int(parts[3])
                        worst = int(parts[4])
                        threshold = int(parts[5])
                        raw_value = int(parts[9].split()[0])  # Take first number from raw value

                        status = 'OK'
                        if normalized <= threshold:
                            status = 'FAIL'
                        elif normalized < threshold + 10:
                            status = 'WARN'

                        attribute = SmartAttribute(
                            id=attr_id,
                            name=attr_name,
                            raw_value=raw_value,
                            normalized_value=normalized,
                            threshold=threshold,
                            worst=worst,
                            status=status,
                            description=self._get_attribute_description(attr_id)
                        )

                        attributes.append(attribute)

                    except (ValueError, IndexError):
                        continue

        return attributes

    def _get_attribute_description(self, attr_id: int) -> str:
        """Get description for SMART attribute ID."""
        descriptions = {
            1: "Read error rate - Rate of hardware read errors",
            2: "Throughput performance - Overall throughput performance",
            3: "Spin up time - Time to spin up to normal speed",
            4: "Start/stop count - Count of spindle start/stop cycles",
            5: "Reallocated sectors count - Count of reallocated sectors",
            6: "Read channel margin - Margin of channel while reading",
            7: "Seek error rate - Rate of seek errors",
            8: "Seek time performance - Performance of seek operations",
            9: "Power-on hours - Hours powered on",
            10: "Spin retry count - Count of retry of spin start attempts",
            11: "Recalibration retries - Count of retries of recalibration",
            12: "Power cycle count - Count of full hard disk power on/off cycles",
            13: "Soft read error rate - Rate of soft read errors",
            181: "Program fail count - Total count of program fails",
            182: "Erase fail count - Total count of erase fails",
            183: "Runtime bad block - Total count of runtime bad blocks",
            184: "End-to-end error - Count of parity errors",
            187: "Reported uncorrectable errors - Count of uncorrectable errors",
            188: "Command timeout - Count of aborted operations due to timeout",
            189: "High fly writes - Count of high fly writes",
            190: "Airflow temperature - Airflow temperature",
            191: "G-sense error rate - Rate of errors as a result of impact loads",
            192: "Power-off retract count - Count of power-off retract events",
            193: "Load cycle count - Count of load/unload cycles",
            194: "Temperature - Current internal temperature",
            195: "Hardware ECC recovered - Count of ECC corrected errors",
            196: "Reallocation event count - Count of reallocation events",
            197: "Current pending sector count - Count of unstable sectors",
            198: "Uncorrectable sector count - Count of uncorrectable errors",
            199: "UltraDMA CRC error count - Count of CRC errors during UltraDMA transfers",
            200: "Multi-zone error rate - Count of errors while writing sectors",
            201: "Soft read error rate - Rate of off-track errors",
            202: "Data address mark errors - Count of data address mark errors",
            203: "Run out candidate - Count of ECC errors",
            204: "Soft ECC correction - Count of soft ECC corrections",
            205: "Thermal asperity rate - Rate of thermal asperity errors",
            206: "Flying height - Height of heads above the disk surface",
            207: "Spin high current - Amount of high current used to spin up drive",
            208: "Spin buzz - Count of buzz routines needed to spin up drive",
            209: "Offline seek performance - Performance of offline seek operations",
            220: "Disk shift - Distance the disk has shifted",
            221: "G-sense error rate - Rate of errors as a result of impact loads",
            222: "Loaded hours - Time spent loaded",
            223: "Load/unload retry count - Count of retry of load/unload attempts",
            224: "Load friction - Resistance caused by friction in the mechanical parts",
            225: "Load/unload cycle count - Count of load/unload cycles",
            226: "Load-in time - Time to load heads",
            227: "Torque amplification count - Count of torque amplification attempts",
            228: "Power-off retract cycle - Count of power-off retract cycles",
            230: "GMR head amplitude - Amplitude of GMR heads",
            231: "Life left - Approximate SSD life left",
            232: "Endurance remaining - Approximate endurance remaining",
            233: "Media wearout indicator - SSD wear indicator",
            234: "Average erase count - Average number of erase operations per block",
            235: "Good block count - Count of good blocks remaining",
            240: "Head flying hours - Time spent with heads flying",
            241: "Total LBAs written - Total count of LBAs written",
            242: "Total LBAs read - Total count of LBAs read"
        }

        return descriptions.get(attr_id, f"Unknown attribute {attr_id}")

    def _get_disk_details(self, device: str) -> Dict[str, Any]:
        """Get basic disk details (model, serial, capacity, etc.)."""
        details = {}

        try:
            # Try smartctl for device info
            result = subprocess.run(
                ['smartctl', '-i', device],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode in [0, 4]:
                output = result.stdout

                # Parse device information
                for line in output.split('\n'):
                    if 'Device Model:' in line:
                        details['model'] = line.split(':', 1)[1].strip()
                    elif 'Serial Number:' in line:
                        details['serial'] = line.split(':', 1)[1].strip()
                    elif 'User Capacity:' in line:
                        # Extract capacity in bytes
                        capacity_str = line.split('[')[1].split()[0] if '[' in line else ''
                        try:
                            details['capacity'] = int(capacity_str.replace(',', ''))
                        except ValueError:
                            pass
                    elif 'SATA' in line:
                        details['interface'] = 'SATA'
                    elif 'NVMe' in line:
                        details['interface'] = 'NVMe'

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: try to get basic info from /sys on Linux
        try:
            import platform
            if platform.system().lower() == 'linux':
                device_name = device.split('/')[-1]
                sys_path = Path(f'/sys/block/{device_name}')

                if sys_path.exists():
                    # Try to get model
                    model_file = sys_path / 'device' / 'model'
                    if model_file.exists():
                        details['model'] = model_file.read_text().strip()

                    # Try to get size
                    size_file = sys_path / 'size'
                    if size_file.exists():
                        size_sectors = int(size_file.read_text().strip())
                        details['capacity'] = size_sectors * 512  # Assume 512-byte sectors

        except Exception:
            pass

        return details

    def _get_performance_metrics(self, device: str) -> Dict[str, float]:
        """Get disk performance metrics."""
        metrics = {}

        try:
            # Get iostat-like metrics using psutil
            disk_io_before = psutil.disk_io_counters(perdisk=True)
            time.sleep(1)  # Wait 1 second
            disk_io_after = psutil.disk_io_counters(perdisk=True)

            device_name = device.split('/')[-1]

            if device_name in disk_io_before and device_name in disk_io_after:
                before = disk_io_before[device_name]
                after = disk_io_after[device_name]

                # Calculate IOPS
                read_iops = after.read_count - before.read_count
                write_iops = after.write_count - before.write_count

                # Calculate throughput in MB/s
                read_mb = (after.read_bytes - before.read_bytes) / (1024 * 1024)
                write_mb = (after.write_bytes - before.write_bytes) / (1024 * 1024)

                # Calculate average times (if available)
                read_time_ms = 0
                write_time_ms = 0

                if hasattr(after, 'read_time') and hasattr(before, 'read_time'):
                    read_time_diff = after.read_time - before.read_time
                    if read_iops > 0:
                        read_time_ms = read_time_diff / read_iops

                if hasattr(after, 'write_time') and hasattr(before, 'write_time'):
                    write_time_diff = after.write_time - before.write_time
                    if write_iops > 0:
                        write_time_ms = write_time_diff / write_iops

                metrics = {
                    'read_iops': read_iops,
                    'write_iops': write_iops,
                    'read_throughput_mbps': read_mb,
                    'write_throughput_mbps': write_mb,
                    'read_latency_ms': read_time_ms,
                    'write_latency_ms': write_time_ms,
                    'utilization_percent': 0  # Would need more complex calculation
                }

        except Exception:
            pass

        return metrics

    def _calculate_health_percentage(self, smart_data: Dict[str, Any]) -> Optional[int]:
        """Calculate overall disk health percentage."""
        if not smart_data.get('attributes'):
            return None

        total_score = 0
        weight_sum = 0

        # Weight critical attributes more heavily
        critical_weights = {
            1: 3,    # Read error rate
            5: 5,    # Reallocated sectors
            10: 3,   # Spin retry count
            196: 4,  # Reallocation events
            197: 5,  # Pending sectors
            198: 5,  # Uncorrectable sectors
            199: 3   # CRC errors
        }

        for attr in smart_data['attributes']:
            weight = critical_weights.get(attr.id, 1)
            weight_sum += weight

            # Calculate attribute health (0-100)
            if attr.threshold > 0:
                attr_health = min(100, (attr.normalized_value / attr.threshold) * 100)
            else:
                attr_health = 100 if attr.status == 'OK' else 0

            total_score += attr_health * weight

        if weight_sum > 0:
            return min(100, int(total_score / weight_sum))

        return None

    def _estimate_life_remaining(self, smart_data: Dict[str, Any], performance: Dict[str, float]) -> Optional[int]:
        """Estimate remaining disk life in months."""
        if not smart_data.get('attributes'):
            return None

        # Look for SSD-specific attributes
        for attr in smart_data['attributes']:
            if attr.id == 231:  # SSD life left
                return int(attr.normalized_value / 100 * 60)  # Assume 5-year typical life
            elif attr.id == 233:  # Media wearout indicator
                if attr.raw_value > 0:
                    wear_percent = (attr.raw_value / 100)
                    remaining_percent = 100 - wear_percent
                    return int(remaining_percent / 100 * 60)  # 5-year life estimate

        # For HDDs, estimate based on power-on hours and reallocated sectors
        power_hours = smart_data.get('power_on_hours')
        reallocated = smart_data.get('reallocated_sectors', 0)

        if power_hours is not None:
            # Typical HDD life: 43,800 hours (5 years)
            expected_life_hours = 43800
            hours_remaining = max(0, expected_life_hours - power_hours)

            # Adjust for reallocated sectors (each reallocated sector reduces life)
            if reallocated > 0:
                penalty_hours = reallocated * 100  # Arbitrary penalty
                hours_remaining = max(0, hours_remaining - penalty_hours)

            return int(hours_remaining / (24 * 30))  # Convert to months

        return None

    def _analyze_smart_warnings(self, smart_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Analyze SMART data for warnings and errors."""
        warnings = []
        errors = []

        if smart_data.get('status') == 'FAILED':
            errors.append("SMART self-test failed")

        for attr in smart_data.get('attributes', []):
            if attr.status == 'FAIL':
                errors.append(f"Critical: {attr.name} (ID {attr.id}) has failed")
            elif attr.status == 'WARN':
                warnings.append(f"Warning: {attr.name} (ID {attr.id}) is degrading")

            # Specific attribute warnings
            if attr.id == 5 and attr.raw_value > 0:  # Reallocated sectors
                if attr.raw_value > 10:
                    errors.append(f"High number of reallocated sectors: {attr.raw_value}")
                else:
                    warnings.append(f"Reallocated sectors detected: {attr.raw_value}")

            elif attr.id == 197 and attr.raw_value > 0:  # Pending sectors
                if attr.raw_value > 5:
                    errors.append(f"High number of pending sectors: {attr.raw_value}")
                else:
                    warnings.append(f"Pending sectors detected: {attr.raw_value}")

            elif attr.id == 198 and attr.raw_value > 0:  # Uncorrectable sectors
                errors.append(f"Uncorrectable sectors detected: {attr.raw_value}")

            elif attr.id == 194:  # Temperature
                if attr.raw_value > 60:
                    errors.append(f"High disk temperature: {attr.raw_value}°C")
                elif attr.raw_value > 50:
                    warnings.append(f"Elevated disk temperature: {attr.raw_value}°C")

        return warnings, errors

    def _get_disk_temperature_linux(self, device: str) -> Optional[int]:
        """Get disk temperature on Linux systems."""
        try:
            # Try hddtemp command
            result = subprocess.run(
                ['hddtemp', device],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Parse hddtemp output: /dev/sda: WDC WD1003FZEX-00MK2A0: 32°C
                output = result.stdout.strip()
                if '°C' in output:
                    temp_str = output.split('°C')[0].split(':')[-1].strip()
                    return int(temp_str)

        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        try:
            # Try smartctl temperature
            result = subprocess.run(
                ['smartctl', '-A', device],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode in [0, 4]:
                for line in result.stdout.split('\n'):
                    if 'Temperature_Celsius' in line or 'Airflow_Temperature_Cel' in line:
                        parts = line.split()
                        if len(parts) >= 10:
                            try:
                                return int(parts[9])
                            except ValueError:
                                pass

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return None

    def get_filesystem_health(self) -> List[FileSystemHealth]:
        """Get file system health information."""
        filesystems = []

        try:
            partitions = psutil.disk_partitions(all=True)

            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)

                    # Get inode information (Unix-like systems)
                    inodes_total = None
                    inodes_used = None
                    inodes_free = None

                    try:
                        import os
                        stat = os.statvfs(partition.mountpoint)
                        inodes_total = stat.f_files
                        inodes_free = stat.f_ffree
                        inodes_used = inodes_total - inodes_free
                    except (AttributeError, OSError):
                        pass

                    filesystem = FileSystemHealth(
                        mount_point=partition.mountpoint,
                        filesystem_type=partition.fstype,
                        total_bytes=usage.total,
                        used_bytes=usage.used,
                        free_bytes=usage.free,
                        used_percent=usage.percent,
                        inodes_total=inodes_total,
                        inodes_used=inodes_used,
                        inodes_free=inodes_free,
                        fragmentation_percent=None,  # Would require filesystem-specific tools
                        last_check=None,  # Would require checking filesystem metadata
                        errors_found=0,  # Would require fsck or equivalent
                        mount_options=partition.opts.split(',') if partition.opts else [],
                        device=partition.device
                    )

                    filesystems.append(filesystem)

                except (PermissionError, OSError):
                    continue

        except Exception:
            pass

        return filesystems

    def export_disk_health_report(self, file_path: Path) -> bool:
        """Export comprehensive disk health report."""
        try:
            disk_health = self.get_disk_health_summary(force_refresh=True)
            filesystem_health = self.get_filesystem_health()

            report_data = {
                "timestamp": int(time.time() * 1000),
                "generated_at": datetime.now().isoformat(),
                "disk_health": [asdict(disk) for disk in disk_health],
                "filesystem_health": [asdict(fs) for fs in filesystem_health],
                "summary": {
                    "total_disks": len(disk_health),
                    "healthy_disks": len([d for d in disk_health if not d.errors]),
                    "disks_with_warnings": len([d for d in disk_health if d.warnings and not d.errors]),
                    "disks_with_errors": len([d for d in disk_health if d.errors]),
                    "total_capacity_gb": sum(d.capacity_bytes for d in disk_health) / (1024**3),
                    "smart_capable_disks": len([d for d in disk_health if d.smart_enabled])
                },
                "metadata": {
                    "smart_library_available": SMART_AVAILABLE,
                    "report_version": "1.0"
                }
            }

            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)

            return True

        except Exception:
            return False