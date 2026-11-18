#!/usr/bin/env bash
# Moni collect-mac.sh - PC device information collector for the Moni viewer (macOS).
#
# What it does:
#   Reads device information from macOS using only the standard tools
#   that ship with the OS (sw_vers, sysctl, system_profiler, diskutil,
#   networksetup, ifconfig, pmset, ioreg) and writes it to
#   "moni-report.json" next to this script, in exactly the same schema
#   as the Windows collector (collect.ps1) and the Linux collector
#   (collect.sh). Read-only: it changes nothing on the Mac and sends
#   nothing over the network. No extra software is required.
#   Items that cannot be collected are written as null, and the viewer
#   displays them honestly as "Unavailable". macOS does not expose some
#   items through its standard tools (motherboard / BIOS details, GPU
#   driver versions); those stay null rather than being guessed. The
#   firmware version is reported as biosVersion when macOS provides one
#   (Boot ROM Version on Intel Macs, System Firmware Version on Apple
#   silicon Macs).
#
# Requires: macOS with bash (the stock /bin/bash 3.2 is fine).
#   No administrator rights needed.
# Version: 1.0.0

# NOTE: no "set -e" on purpose. A failed probe must never abort the
# whole collection; whatever could not be read simply becomes null.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
if [ -z "$SCRIPT_DIR" ]; then SCRIPT_DIR="$(pwd)"; fi
OUT_PATH="$SCRIPT_DIR/moni-report.json"

# ---------- small helpers (same as collect.sh) ----------

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

jescape() { # escape a string for inclusion in JSON double quotes
  local s="$1"
  s="$(printf '%s' "$s" | tr -d '\000-\010\013\014\016-\037\177')"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/ }"
  s="${s//$'\r'/ }"
  s="${s//$'\t'/ }"
  printf '%s' "$s"
}

jstr() { # string or null; placeholder strings count as missing
  local v
  v="$(trim "$1")"
  case "$v" in
    "" | "Not Specified" | "Not Applicable" | "To Be Filled By O.E.M." | \
    "Default string" | "None" | "Unknown")
      printf 'null'; return ;;
  esac
  printf '"%s"' "$(jescape "$v")"
}

jstr_plain() { # string or null (only emptiness counts as missing)
  local v
  v="$(trim "$1")"
  if [ -z "$v" ]; then printf 'null'; return; fi
  printf '"%s"' "$(jescape "$v")"
}

jnum_pos() { # positive integer or null
  case "$1" in
    '' | *[!0-9]*) printf 'null' ;;
    *) if [ "$1" -gt 0 ] 2>/dev/null; then printf '%s' "$1"; else printf 'null'; fi ;;
  esac
}

jnum_nonneg() { # non-negative integer or null (0 is a real value here)
  case "$1" in
    '' | *[!0-9]*) printf 'null' ;;
    *) printf '%s' "$1" ;;
  esac
}

join_fragments() { # join "$@" with commas (JSON array elements)
  local out="" f
  for f in "$@"; do
    if [ -n "$out" ]; then out="$out,$f"; else out="$f"; fi
  done
  printf '%s' "$out"
}

echo 'Moni: PC のデバイス情報を収集しています...'

# Hardware overview from system_profiler, parsed several times below.
sp_hw="$(system_profiler SPHardwareDataType 2>/dev/null)"
sp_hw_get() { # $1 = field name in SPHardwareDataType -> value
  printf '%s\n' "$sp_hw" | sed -n "s/^[[:space:]]*$1:[[:space:]]*//p" | head -n 1
}

# ---------- System ----------
sys_computer="$(scutil --get ComputerName 2>/dev/null)"
if [ -z "$(trim "$sys_computer")" ]; then sys_computer="$(hostname 2>/dev/null)"; fi
# The manufacturer of a Mac is Apple; the model name (e.g. "MacBook Pro")
# comes from system_profiler, with the model identifier as fallback.
sys_manufacturer="Apple"
sys_model="$(sp_hw_get "Model Name")"
if [ -z "$(trim "$sys_model")" ]; then sys_model="$(sysctl -n hw.model 2>/dev/null)"; fi
sys_os_name="$(sw_vers -productName 2>/dev/null)"
sys_os_version="$(sw_vers -productVersion 2>/dev/null)"
sys_os_build="$(sw_vers -buildVersion 2>/dev/null)"
# kern.boottime looks like "{ sec = 1699999999, usec = 0 } ..."; the
# "{ sec =" anchor keeps the match away from the "usec" value.
boot_sec="$(sysctl -n kern.boottime 2>/dev/null | sed -n 's/.*{ sec = \([0-9][0-9]*\),.*/\1/p' | head -n 1)"
sys_uptime=""
case "$boot_sec" in
  '' | *[!0-9]*) ;;
  *)
    now_sec="$(date +%s 2>/dev/null)"
    case "$now_sec" in
      '' | *[!0-9]*) ;;
      *) if [ "$now_sec" -gt "$boot_sec" ] 2>/dev/null; then sys_uptime=$((now_sec - boot_sec)); fi ;;
    esac
    ;;
esac

system_json="{\"computerName\":$(jstr_plain "$sys_computer"),\"manufacturer\":$(jstr_plain "$sys_manufacturer"),\"model\":$(jstr_plain "$sys_model"),\"osName\":$(jstr_plain "$sys_os_name"),\"osVersion\":$(jstr_plain "$sys_os_version"),\"osBuild\":$(jstr_plain "$sys_os_build"),\"uptimeSeconds\":$(jnum_pos "$sys_uptime")}"

# ---------- CPU ----------
# Intel Macs expose the brand string via sysctl; Apple silicon Macs do
# not, so the chip name is taken from system_profiler instead.
cpu_name="$(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
if [ -z "$(trim "$cpu_name")" ]; then cpu_name="$(sp_hw_get "Chip")"; fi
if [ -z "$(trim "$cpu_name")" ]; then cpu_name="$(sp_hw_get "Processor Name")"; fi
cpu_cores="$(sysctl -n hw.physicalcpu 2>/dev/null)"
cpu_logical="$(sysctl -n hw.logicalcpu 2>/dev/null)"
if [ -z "$(trim "$cpu_logical")" ]; then cpu_logical="$(sysctl -n hw.ncpu 2>/dev/null)"; fi
# Nominal frequency in Hz (Intel only; absent on Apple silicon -> null).
cpu_hz="$(sysctl -n hw.cpufrequency_max 2>/dev/null)"
if [ -z "$(trim "$cpu_hz")" ]; then cpu_hz="$(sysctl -n hw.cpufrequency 2>/dev/null)"; fi
cpu_max_mhz=""
case "$cpu_hz" in
  '' | *[!0-9]*) ;;
  *) cpu_max_mhz=$((cpu_hz / 1000000)) ;;
esac

cpu_json="{\"name\":$(jstr_plain "$cpu_name"),\"cores\":$(jnum_pos "$cpu_cores"),\"logicalProcessors\":$(jnum_pos "$cpu_logical"),\"maxClockMHz\":$(jnum_pos "$cpu_max_mhz")}"

# ---------- Memory ----------
mem_total="$(sysctl -n hw.memsize 2>/dev/null)"

mem_fragments=()
# Per-module details come from system_profiler SPMemoryDataType. Macs
# with soldered / unified memory may report no module blocks; the list
# then honestly stays empty (the total above still comes from sysctl).
sp_mem="$(system_profiler SPMemoryDataType 2>/dev/null)"
mem_tsv="$(printf '%s\n' "$sp_mem" | awk '
  function flush() {
    if (size_bytes > 0) {
      printf "%s\t%s\t%s\t%s\t%s\n", size_bytes, mtype, speed, maker, part
    }
    size_bytes = 0; mtype = ""; speed = ""; maker = ""; part = ""
  }
  /^    [^ ].*:$/ { flush(); next }
  /^      Size:/ {
    v = $0; sub(/^      Size:[[:space:]]*/, "", v)
    n = split(v, a, " ")
    size_bytes = 0
    if (n >= 2 && a[1] ~ /^[0-9]+$/) {
      mult = 0
      if (a[2] == "KB") mult = 1024
      else if (a[2] == "MB") mult = 1048576
      else if (a[2] == "GB") mult = 1073741824
      else if (a[2] == "TB") mult = 1099511627776
      size_bytes = a[1] * mult
    }
  }
  /^      Type:/ { v = $0; sub(/^      Type:[[:space:]]*/, "", v); if (v != "Unknown") mtype = v }
  /^      Speed:/ {
    v = $0; sub(/^      Speed:[[:space:]]*/, "", v)
    if (v ~ /^[0-9]+/) { match(v, /^[0-9]+/); speed = substr(v, 1, RLENGTH) }
  }
  /^      Manufacturer:/ { v = $0; sub(/^      Manufacturer:[[:space:]]*/, "", v); maker = v }
  /^      Part Number:/ { v = $0; sub(/^      Part Number:[[:space:]]*/, "", v); part = v }
  END { flush() }
')"
if [ -n "$mem_tsv" ]; then
  while IFS="$(printf '\t')" read -r m_bytes m_type m_speed m_maker m_part; do
    [ -n "$m_bytes" ] || continue
    mem_fragments+=("{\"capacityBytes\":$(jnum_pos "$m_bytes"),\"type\":$(jstr "$m_type"),\"speedMHz\":$(jnum_pos "$m_speed"),\"manufacturer\":$(jstr "$m_maker"),\"partNumber\":$(jstr "$m_part")}")
  done <<EOF
$mem_tsv
EOF
fi
memory_json="{\"totalBytes\":$(jnum_pos "$mem_total"),\"modules\":[$(join_fragments "${mem_fragments[@]}")]}"

# ---------- GPU ----------
# system_profiler SPDisplaysDataType lists each GPU with a "Chipset
# Model" and, for discrete / Intel GPUs, a VRAM figure. Apple silicon
# GPUs share system memory and report no VRAM, and macOS exposes no GPU
# driver version through its standard tools: both stay null.
sp_displays="$(system_profiler SPDisplaysDataType 2>/dev/null)"

gpu_fragments=()
gpu_tsv="$(printf '%s\n' "$sp_displays" | awk '
  function flush() {
    if (name != "") printf "%s\t%s\n", name, vram
    name = ""; vram = ""
  }
  /^    [^ ].*:$/ { flush(); next }
  /^      Chipset Model:/ { v = $0; sub(/^      Chipset Model:[[:space:]]*/, "", v); name = v }
  /^      VRAM \(/ {
    v = $0; sub(/^[^:]*:[[:space:]]*/, "", v)
    n = split(v, a, " ")
    vram = ""
    if (n >= 2 && a[1] ~ /^[0-9]+$/) {
      if (a[2] == "MB") vram = a[1] * 1048576
      else if (a[2] == "GB") vram = a[1] * 1073741824
      else if (a[2] == "TB") vram = a[1] * 1099511627776
    }
  }
  END { flush() }
')"
if [ -n "$gpu_tsv" ]; then
  while IFS="$(printf '\t')" read -r g_name g_vram; do
    [ -n "$g_name" ] || continue
    gpu_fragments+=("{\"name\":$(jstr_plain "$g_name"),\"vramBytes\":$(jnum_pos "$g_vram"),\"driverVersion\":null}")
  done <<EOF
$gpu_tsv
EOF
fi
gpus_json="[$(join_fragments "${gpu_fragments[@]}")]"

# ---------- Displays ----------
# Parsed from the "Displays:" subsection of SPDisplaysDataType. The
# refresh rate is only present in the output for some displays (as part
# of a "Resolution: ... @ 60 Hz" or "UI Looks like: ... @ 60.00Hz"
# line); when it is not printed it stays null.
disp_fragments=()
disp_tsv="$(printf '%s\n' "$sp_displays" | awk '
  function flush() {
    if (name != "") printf "%s\t%s\t%s\t%s\n", name, w, h, ref
    name = ""; w = ""; h = ""; ref = ""
  }
  /^    [^ ].*:$/ { flush(); in_disp = 0; next }
  /^      Displays:$/ { in_disp = 1; next }
  in_disp && /^        [^ ].*:$/ {
    flush()
    name = $0
    sub(/^[[:space:]]*/, "", name); sub(/[[:space:]]*:$/, "", name)
    next
  }
  in_disp && /^          / {
    if (w == "" && $0 ~ /Resolution:/ && match($0, /[0-9]+ x [0-9]+/)) {
      s = substr($0, RSTART, RLENGTH)
      split(s, a, " x ")
      w = a[1]; h = a[2]
    }
    if (ref == "" && match($0, /@[[:space:]]*[0-9.]+[[:space:]]*Hz/)) {
      s = substr($0, RSTART, RLENGTH)
      gsub(/[@ Hz]/, "", s)
      ref = int(s)
    }
  }
  END { flush() }
')"
if [ -n "$disp_tsv" ]; then
  while IFS="$(printf '\t')" read -r d_name d_w d_h d_ref; do
    [ -n "$d_name" ] || continue
    disp_fragments+=("{\"name\":$(jstr_plain "$d_name"),\"width\":$(jnum_pos "$d_w"),\"height\":$(jnum_pos "$d_h"),\"refreshRateHz\":$(jnum_pos "$d_ref")}")
  done <<EOF
$disp_tsv
EOF
fi
displays_json="[$(join_fragments "${disp_fragments[@]}")]"

# ---------- Motherboard / BIOS ----------
# macOS does not expose a motherboard or a BIOS through its standard
# tools, so those fields stay null. The firmware version is the closest
# equivalent of a BIOS version and is reported when present.
mb_bios_version="$(sp_hw_get "Boot ROM Version")"
if [ -z "$(trim "$mb_bios_version")" ]; then mb_bios_version="$(sp_hw_get "System Firmware Version")"; fi
mb_bios_version="${mb_bios_version%% (*}" # drop any " (iBridge: ...)" suffix
motherboard_json="{\"manufacturer\":null,\"product\":null,\"biosVersion\":$(jstr_plain "$mb_bios_version"),\"biosDate\":null}"

# ---------- Storage ----------
phys_fragments=()
disk_ids="$(diskutil list physical 2>/dev/null | awk '/^\/dev\//{print $1}')"
for dnode in $disk_ids; do
  d_info="$(diskutil info "$dnode" 2>/dev/null)"
  [ -n "$d_info" ] || continue
  d_model="$(printf '%s\n' "$d_info" | sed -n 's|^[[:space:]]*Device / Media Name:[[:space:]]*||p' | head -n 1)"
  d_size="$(printf '%s\n' "$d_info" | sed -n 's/^[[:space:]]*Disk Size:.*(\([0-9][0-9]*\) Bytes).*/\1/p' | head -n 1)"
  d_solid="$(printf '%s\n' "$d_info" | sed -n 's/^[[:space:]]*Solid State:[[:space:]]*//p' | head -n 1)"
  d_proto="$(printf '%s\n' "$d_info" | sed -n 's/^[[:space:]]*Protocol:[[:space:]]*//p' | head -n 1)"
  case "$(trim "$d_solid")" in
    Yes) media_json='"SSD"' ;;
    No) media_json='"HDD"' ;;
    *) media_json='null' ;;
  esac
  case "$(trim "$d_proto")" in
    "") bus_json='null' ;;
    # The internal SSD of a Mac connects over PCIe with NVMe.
    "PCI-Express") bus_json='"NVMe"' ;;
    *) bus_json="$(jstr_plain "$d_proto")" ;;
  esac
  # SMART summary: diskutil reports only the overall status ("Verified"
  # / "Failing" / "Not Supported"); macOS exposes no temperature or
  # power-on counters through its standard tools, so those stay null.
  d_smart="$(printf '%s\n' "$d_info" | sed -n 's/^[[:space:]]*SMART Status:[[:space:]]*//p' | head -n 1)"
  case "$(trim "$d_smart")" in
    Verified) smart_json='{"status":"ok","temperatureC":null,"powerOnHours":null,"powerOnCount":null}' ;;
    Failing) smart_json='{"status":"critical","temperatureC":null,"powerOnHours":null,"powerOnCount":null}' ;;
    *) smart_json='{"status":null,"temperatureC":null,"powerOnHours":null,"powerOnCount":null}' ;;
  esac
  phys_fragments+=("{\"model\":$(jstr "$d_model"),\"sizeBytes\":$(jnum_pos "$d_size"),\"mediaType\":$media_json,\"busType\":$bus_json,\"smart\":$smart_json}")
done

# Filesystem types per mount point, from the mount table.
mount_map="$(mount 2>/dev/null | awk '{
  oi = index($0, " on "); if (!oi) next
  rest = substr($0, oi + 4)
  pos = 0; i = 1
  while ((j = index(substr(rest, i), " (")) > 0) { pos = i + j - 1; i = pos + 2 }
  if (!pos) next
  mp = substr(rest, 1, pos - 1)
  fs = substr(rest, pos + 2)
  sub(/,.*/, "", fs); sub(/\)$/, "", fs)
  printf "%s\t%s\n", mp, fs
}')"
fs_of() { # $1 = mount point -> filesystem type (empty when unknown)
  printf '%s\n' "$mount_map" | awk -F '\t' -v m="$1" '$1 == m {print $2; exit}'
}

log_fragments=()
seen_mounts=""
while IFS= read -r line; do
  [ -n "$line" ] || continue
  # df -k -P columns: source total used avail capacity mountpoint...
  set -- $line
  [ "$#" -ge 6 ] || continue
  l_source="$1"; l_total_k="$2"; l_avail_k="$4"
  shift 5; l_mount="$*"
  case "$l_total_k" in '' | *[!0-9]*) continue ;; esac
  case "$l_avail_k" in '' | *[!0-9]*) continue ;; esac
  case "$l_source" in devfs | map | map\ *) continue ;; esac
  l_fstype="$(fs_of "$l_mount")"
  case "$l_fstype" in
    devfs | autofs | fdesc | kernfs | procfs) continue ;;
  esac
  # APFS system helper volumes are managed by macOS itself; only the
  # system volume ("/") and the user data volume are listed, like the
  # pseudo filesystems the Linux collector skips.
  case "$l_mount" in
    /System/Volumes/*)
      [ "$l_mount" = "/System/Volumes/Data" ] || continue
      ;;
  esac
  dedupe_key="$l_source|$l_total_k"
  case "|$seen_mounts|" in *"|$dedupe_key|"*) continue ;; esac
  seen_mounts="$seen_mounts|$dedupe_key"
  case "$l_fstype" in
    apfs) fs_json='"APFS"' ;;
    hfs) fs_json='"HFS+"' ;;
    "") fs_json='null' ;;
    *) fs_json="$(jstr_plain "$l_fstype")" ;;
  esac
  l_label=""
  case "$l_source" in
    /dev/*)
      l_label="$(diskutil info "$l_source" 2>/dev/null | sed -n 's|^[[:space:]]*Volume Name:[[:space:]]*||p' | head -n 1)"
      case "$l_label" in *"Not applicable"*) l_label="" ;; esac
      ;;
  esac
  l_total=$((l_total_k * 1024))
  l_free=$((l_avail_k * 1024))
  log_fragments+=("{\"drive\":$(jstr_plain "$l_mount"),\"label\":$(jstr "$l_label"),\"fileSystem\":$fs_json,\"totalBytes\":$(jnum_pos "$l_total"),\"freeBytes\":$(jnum_nonneg "$l_free")}")
done <<EOF
$(df -k -P 2>/dev/null | tail -n +2)
EOF
storage_json="{\"physical\":[$(join_fragments "${phys_fragments[@]}")],\"logical\":[$(join_fragments "${log_fragments[@]}")]}"

# ---------- Network ----------
# Physical adapters only, from networksetup's hardware port list (the
# loopback interface is not a hardware port and never appears here).
net_fragments=()
hw_name=""
hw_pairs=()
while IFS= read -r line; do
  case "$line" in
    "VLAN"*) break ;;
    "Hardware Port: "*) hw_name="${line#Hardware Port: }" ;;
    "Device: "*)
      hw_dev="${line#Device: }"
      if [ -n "$hw_dev" ]; then hw_pairs+=("$hw_dev|$hw_name"); fi
      ;;
  esac
done <<EOF
$(networksetup -listallhardwareports 2>/dev/null)
EOF
for pair in "${hw_pairs[@]}"; do
  n_dev="${pair%%|*}"
  n_desc="${pair#*|}"
  ifc="$(ifconfig "$n_dev" 2>/dev/null)"
  [ -n "$ifc" ] || continue
  n_mac_raw="$(printf '%s\n' "$ifc" | awk '/^[[:space:]]*ether[[:space:]]/{print $2; exit}')"
  if [ -z "$n_mac_raw" ] || [ "$n_mac_raw" = "00:00:00:00:00:00" ]; then
    n_mac_json='null'
  else
    n_mac="$(printf '%s' "$n_mac_raw" | tr 'a-f' 'A-F' | tr ':' '-')"
    n_mac_json="$(jstr_plain "$n_mac")"
  fi
  n_status_raw="$(printf '%s\n' "$ifc" | awk -F': ' '/^[[:space:]]*status:/{print $2; exit}')"
  case "$(trim "$n_status_raw")" in
    active) n_status="Up" ;;
    inactive) n_status="Disconnected" ;;
    *) n_status="" ;;
  esac
  ipv4_fragments=()
  while IFS= read -r addr; do
    [ -n "$addr" ] && ipv4_fragments+=("$(jstr_plain "$addr")")
  done <<EOF
$(printf '%s\n' "$ifc" | awk '$1 == "inet" {print $2}')
EOF
  ipv6_fragments=()
  while IFS= read -r addr; do
    [ -n "$addr" ] && ipv6_fragments+=("$(jstr_plain "$addr")")
  done <<EOF
$(printf '%s\n' "$ifc" | awk '$1 == "inet6" {a = $2; sub(/%.*/, "", a); print a}')
EOF
  media_tok="$(printf '%s\n' "$ifc" | sed -n 's/^[[:space:]]*media: [^(]*(\([A-Za-z0-9]*\).*/\1/p' | head -n 1)"
  if [ -z "$media_tok" ]; then
    media_tok="$(printf '%s\n' "$ifc" | sed -n 's/^[[:space:]]*media: \([A-Za-z0-9]*\).*/\1/p' | head -n 1)"
    case "$media_tok" in *base*) ;; *) media_tok="" ;; esac
  fi
  case "$media_tok" in
    10baseT | 10baseT/UTP) n_speed="10" ;;
    100baseTX | 100baseT) n_speed="100" ;;
    1000baseT) n_speed="1000" ;;
    2500baseT) n_speed="2500" ;;
    5000baseT) n_speed="5000" ;;
    10GbaseT) n_speed="10000" ;;
    25GbaseT) n_speed="25000" ;;
    40GbaseT) n_speed="40000" ;;
    *) n_speed="" ;;
  esac
  net_fragments+=("{\"name\":$(jstr_plain "$n_dev"),\"description\":$(jstr_plain "$n_desc"),\"status\":$(jstr_plain "$n_status"),\"ipv4\":[$(join_fragments "${ipv4_fragments[@]}")],\"ipv6\":[$(join_fragments "${ipv6_fragments[@]}")],\"macAddress\":$n_mac_json,\"linkSpeedMbps\":$(jnum_pos "$n_speed")}")
done
network_json="[$(join_fragments "${net_fragments[@]}")]"

# ---------- Battery ----------
battery_json='null'
batt_out="$(pmset -g batt 2>/dev/null)"
case "$batt_out" in
  *InternalBattery*)
    b_line="$(printf '%s\n' "$batt_out" | grep 'InternalBattery' | head -n 1)"
    b_pct="$(printf '%s' "$b_line" | sed -n 's/.*[[:space:]]\([0-9][0-9]*\)%;.*/\1/p')"
    b_status_raw="$(trim "$(printf '%s' "$b_line" | awk -F';' '{print $2}')")"
    case "$b_status_raw" in
      *discharging*) b_status="Discharging" ;;
      *charging*) b_status="Charging" ;;
      *charged*) b_status="Charged" ;;
      *) b_status="$b_status_raw" ;;
    esac
    # Capacities: ioreg reports charge in mAh and voltage in mV, so
    # mWh = mAh * mV / 1000. Any missing value leaves both capacities
    # null instead of estimating them.
    ioreg_out="$(ioreg -r -c AppleSmartBattery -w 0 2>/dev/null)"
    d_mah="$(printf '%s\n' "$ioreg_out" | sed -n 's/.*"DesignCapacity" = \([0-9][0-9]*\).*/\1/p' | head -n 1)"
    f_mah="$(printf '%s\n' "$ioreg_out" | sed -n 's/.*"AppleRawMaxCapacity" = \([0-9][0-9]*\).*/\1/p' | head -n 1)"
    volt_mv="$(printf '%s\n' "$ioreg_out" | sed -n 's/.*"Voltage" = \([0-9][0-9]*\).*/\1/p' | head -n 1)"
    b_design=""; b_full=""
    case "$d_mah" in '' | *[!0-9]*) ;; *)
      case "$volt_mv" in '' | *[!0-9]*) ;; *)
        if [ "$d_mah" -gt 0 ] 2>/dev/null && [ "$volt_mv" -gt 0 ] 2>/dev/null; then
          b_design=$((d_mah * volt_mv / 1000))
        fi
        case "$f_mah" in '' | *[!0-9]*) ;; *)
          if [ "$f_mah" -gt 0 ] 2>/dev/null; then
            b_full=$((f_mah * volt_mv / 1000))
          fi
          ;;
        esac
        ;;
      esac
      ;;
    esac
    battery_json="{\"chargePercent\":$(jnum_nonneg "$b_pct"),\"status\":$(jstr_plain "$b_status"),\"designCapacityMWh\":$(jnum_pos "$b_design"),\"fullChargeCapacityMWh\":$(jnum_pos "$b_full")}"
    ;;
esac

# ---------- USB / peripherals ----------
# Parsed from system_profiler SPUSBDataType: every block that carries a
# "Product ID" is a USB device (hubs included, as in the other
# collectors). The description is the manufacturer string the device
# itself reports, when it reports one.
peri_fragments=()
sp_usb="$(system_profiler SPUSBDataType 2>/dev/null)"
usb_tsv="$(printf '%s\n' "$sp_usb" | awk '
  function emit(level) {
    if (pid[level] != "") printf "%s\t%s\n", nm[level], mk[level]
    pid[level] = ""; mk[level] = ""; nm[level] = ""
  }
  function flush_from(level,    i) {
    for (i = level; i <= maxlev; i++) if (nm[i] != "") emit(i)
  }
  {
    indent = 0
    while (substr($0, indent + 1, 1) == " ") indent++
    t = substr($0, indent + 1)
    sub(/[[:space:]]+$/, "", t)
    if (t == "") next
    if (t ~ /:$/) {
      flush_from(indent)
      name = t; sub(/:$/, "", name)
      nm[indent] = name; pid[indent] = ""; mk[indent] = ""
      cur = indent
      if (indent > maxlev) maxlev = indent
    } else if (t ~ /^Product ID:/) {
      pid[cur] = "1"
    } else if (t ~ /^Manufacturer:/) {
      v = t; sub(/^Manufacturer:[[:space:]]*/, "", v); mk[cur] = v
    }
  }
  END { flush_from(0) }
')"
if [ -n "$usb_tsv" ]; then
  while IFS="$(printf '\t')" read -r p_name p_maker; do
    [ -n "$p_name" ] || continue
    peri_fragments+=("{\"name\":$(jstr_plain "$p_name"),\"description\":$(jstr_plain "$p_maker")}")
  done <<EOF
$usb_tsv
EOF
fi
peripherals_json="[$(join_fragments "${peri_fragments[@]}")]"

# ---------- Assemble & write ----------
collected_at="$(date +"%Y-%m-%dT%H:%M:%S%z" 2>/dev/null | sed 's/\([+-][0-9][0-9]\)\([0-9][0-9]\)$/\1:\2/')"

report="{\"format\":\"moni-report\",\"version\":1,\"collectedAt\":$(jstr_plain "$collected_at"),\"collector\":\"Moni collect-mac.sh 1.0.0\",\"sampleData\":false,\"system\":$system_json,\"cpu\":$cpu_json,\"memory\":$memory_json,\"gpus\":$gpus_json,\"motherboard\":$motherboard_json,\"storage\":$storage_json,\"network\":$network_json,\"displays\":$displays_json,\"battery\":$battery_json,\"peripherals\":$peripherals_json}"

printf '%s\n' "$report" > "$OUT_PATH"

echo ''
echo "完了しました: $OUT_PATH"
echo 'このファイルを Moni の index.html で開くと、デバイス情報を確認できます。'
echo '情報はこの PC の中だけに保存され、外部へ送信されることはありません。'
