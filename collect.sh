#!/usr/bin/env bash
# Moni collect.sh - PC device information collector for the Moni viewer (Linux).
#
# What it does:
#   Reads device information from Linux (/proc, /sys, and a few standard
#   read-only commands) and writes it to "moni-report.json" next to this
#   script, in exactly the same schema as the Windows collector
#   (collect.ps1). Read-only: it changes nothing on the PC and sends
#   nothing over the network. No extra software is required beyond a
#   normal Linux install (bash + coreutils); optional tools such as
#   dmidecode / lspci / xrandr are used only when already present.
#   Items that cannot be collected are written as null, and the viewer
#   displays them honestly as "Unavailable".
#
# Requires: Linux with bash. No root / administrator rights needed
#   (a few items, e.g. memory module details via dmidecode, may stay
#   unavailable without root; they are reported as null, never guessed).
# Version: 1.0.0

# NOTE: no "set -e" on purpose. A failed probe must never abort the
# whole collection; whatever could not be read simply becomes null.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
if [ -z "$SCRIPT_DIR" ]; then SCRIPT_DIR="$(pwd)"; fi
OUT_PATH="$SCRIPT_DIR/moni-report.json"

DMI_DIR="/sys/class/dmi/id"
if [ ! -d "$DMI_DIR" ]; then DMI_DIR="/sys/devices/virtual/dmi/id"; fi

# ---------- small helpers ----------

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

read_file() { # $1 = path -> file content (empty when unreadable)
  if [ -r "$1" ]; then cat -- "$1" 2>/dev/null; fi
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

jstr() { # string or null; firmware placeholder strings count as missing
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

osr_get() { # $1 = key in os-release -> value (unquoted)
  local f v
  for f in /etc/os-release /usr/lib/os-release; do
    if [ -r "$f" ]; then
      v="$(grep -E "^$1=" "$f" 2>/dev/null | head -n 1 | cut -d= -f2-)"
      if [ -n "$v" ]; then
        v="${v%\"}"; v="${v#\"}"
        v="${v%\'}"; v="${v#\'}"
        printf '%s' "$v"
        return
      fi
    fi
  done
}

echo 'Moni: PC のデバイス情報を収集しています...'

# ---------- System ----------
sys_computer="$(hostname 2>/dev/null)"
if [ -z "$sys_computer" ]; then sys_computer="$(read_file /etc/hostname)"; fi
if [ -z "$sys_computer" ]; then sys_computer="${HOSTNAME:-}"; fi
sys_manufacturer="$(read_file "$DMI_DIR/sys_vendor")"
sys_model="$(read_file "$DMI_DIR/product_name")"
sys_os_name="$(osr_get PRETTY_NAME)"
if [ -z "$sys_os_name" ]; then sys_os_name="$(osr_get NAME)"; fi
sys_os_version="$(osr_get VERSION_ID)"
sys_os_build="$(uname -r 2>/dev/null)"
sys_uptime="$(awk '{printf "%d", $1}' /proc/uptime 2>/dev/null)"

system_json="{\"computerName\":$(jstr_plain "$sys_computer"),\"manufacturer\":$(jstr "$sys_manufacturer"),\"model\":$(jstr "$sys_model"),\"osName\":$(jstr_plain "$sys_os_name"),\"osVersion\":$(jstr_plain "$sys_os_version"),\"osBuild\":$(jstr_plain "$sys_os_build"),\"uptimeSeconds\":$(jnum_pos "$sys_uptime")}"

# ---------- CPU ----------
cpu_name="$(awk -F: '/^model name/{v=$2; sub(/^[ \t]+/, "", v); print v; exit}' /proc/cpuinfo 2>/dev/null)"
if [ -z "$cpu_name" ] && command -v lscpu >/dev/null 2>&1; then
  cpu_name="$(lscpu 2>/dev/null | awk -F: '/^Model name/{v=$2; sub(/^[ \t]+/, "", v); print v; exit}')"
fi
if [ -z "$cpu_name" ]; then
  cpu_name="$(awk -F: '/^Hardware/{v=$2; sub(/^[ \t]+/, "", v); print v; exit}' /proc/cpuinfo 2>/dev/null)"
fi

cpu_cores="$(awk -F: '/^cpu cores/{v=$2; sub(/[^0-9]/, "", v); print v; exit}' /proc/cpuinfo 2>/dev/null)"
if [ -z "$cpu_cores" ] && command -v lscpu >/dev/null 2>&1; then
  lscpu_out="$(lscpu 2>/dev/null)"
  cps="$(printf '%s\n' "$lscpu_out" | awk -F: '/^Core\(s\) per socket/{v=$2; sub(/[^0-9]/, "", v); print v; exit}')"
  socks="$(printf '%s\n' "$lscpu_out" | awk -F: '/^Socket\(s\)/{v=$2; sub(/[^0-9]/, "", v); print v; exit}')"
  if [ -n "$cps" ] && [ -n "$socks" ]; then cpu_cores=$((cps * socks)); fi
fi
if [ -z "$cpu_cores" ] || [ "$cpu_cores" = "0" ]; then
  pairs="$(awk '/^physical id/{p=$NF} /^core id/{print p ":" $NF}' /proc/cpuinfo 2>/dev/null | sort -u | grep -c .)"
  if [ -n "$pairs" ] && [ "$pairs" != "0" ]; then cpu_cores="$pairs"; else cpu_cores=""; fi
fi

cpu_logical="$(grep -c '^processor' /proc/cpuinfo 2>/dev/null)"
if [ -z "$cpu_logical" ] || [ "$cpu_logical" = "0" ]; then
  cpu_logical="$(nproc 2>/dev/null)"
fi
if [ -z "$cpu_logical" ] || [ "$cpu_logical" = "0" ]; then
  cpu_logical="$(getconf _NPROCESSORS_ONLN 2>/dev/null)"
fi

cpu_max_mhz=""
for f in /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq \
         /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq; do
  khz="$(read_file "$f")"
  khz="$(trim "$khz")"
  case "$khz" in
    '' | *[!0-9]*) ;;
    *) cpu_max_mhz=$((khz / 1000)); break ;;
  esac
done
if [ -z "$cpu_max_mhz" ] && command -v lscpu >/dev/null 2>&1; then
  mhzf="$(lscpu 2>/dev/null | awk -F: '/^CPU max MHz/{v=$2; sub(/^[ \t]+/, "", v); print v; exit}')"
  cpu_max_mhz="${mhzf%%.*}"
fi

cpu_json="{\"name\":$(jstr_plain "$cpu_name"),\"cores\":$(jnum_pos "$cpu_cores"),\"logicalProcessors\":$(jnum_pos "$cpu_logical"),\"maxClockMHz\":$(jnum_pos "$cpu_max_mhz")}"

# ---------- Memory ----------
mem_total="$(awk '/^MemTotal:/{print $2 * 1024; exit}' /proc/meminfo 2>/dev/null)"

mem_fragments=()
# Per-module details need firmware data. dmidecode exposes them but is
# often root-only; when it is unavailable or unreadable the module list
# honestly stays empty (total capacity above still comes from /proc).
if command -v dmidecode >/dev/null 2>&1; then
  dmi_mem="$(dmidecode -t memory 2>/dev/null | awk '
    function flush() {
      if (size_bytes > 0) {
        printf "%s\t%s\t%s\t%s\t%s\n", size_bytes, mtype, speed, maker, part
      }
      size_bytes = 0; mtype = ""; speed = ""; maker = ""; part = ""
    }
    /^Memory Device$/ { flush() }
    /^\tSize:/ {
      line = $0; sub(/^\tSize:[ \t]*/, "", line)
      if (line ~ /^(No Module Installed|Unknown|0)/) { size_bytes = 0 }
      else {
        n = split(line, a, " ")
        if (n >= 2) {
          mult = 1
          if (a[2] == "kB") mult = 1024
          else if (a[2] == "MB") mult = 1048576
          else if (a[2] == "GB") mult = 1073741824
          else if (a[2] == "TB") mult = 1099511627776
          size_bytes = a[1] * mult
        }
      }
    }
    /^\tType:/ { if ($2 != "Unknown") mtype = $2 }
    /^\tSpeed:/ { if ($2 ~ /^[0-9]+$/) speed = $2 }
    /^\tManufacturer:/ { v = $0; sub(/^\tManufacturer:[ \t]*/, "", v); maker = v }
    /^\tPart Number:/ { v = $0; sub(/^\tPart Number:[ \t]*/, "", v); part = v }
    END { flush() }
  ')"
  if [ -n "$dmi_mem" ]; then
    while IFS="$(printf '\t')" read -r m_bytes m_type m_speed m_maker m_part; do
      [ -n "$m_bytes" ] || continue
      mem_fragments+=("{\"capacityBytes\":$(jnum_pos "$m_bytes"),\"type\":$(jstr "$m_type"),\"speedMHz\":$(jnum_pos "$m_speed"),\"manufacturer\":$(jstr "$m_maker"),\"partNumber\":$(jstr "$m_part")}")
    done <<EOF
$dmi_mem
EOF
  fi
fi
if [ "${#mem_fragments[@]}" -eq 0 ]; then
  # EDAC fallback: capacity and type per DIMM, when the kernel exposes it.
  for dimm in /sys/devices/system/edac/mc/mc*/dimm*; do
    [ -d "$dimm" ] || continue
    d_size_mb="$(trim "$(read_file "$dimm/size")")"
    case "$d_size_mb" in '' | *[!0-9]*) continue ;; esac
    [ "$d_size_mb" -gt 0 ] 2>/dev/null || continue
    d_bytes=$((d_size_mb * 1048576))
    d_type="$(read_file "$dimm/dimm_mem_type")"
    mem_fragments+=("{\"capacityBytes\":$(jnum_pos "$d_bytes"),\"type\":$(jstr "$d_type"),\"speedMHz\":null,\"manufacturer\":null,\"partNumber\":null}")
  done
fi
memory_json="{\"totalBytes\":$(jnum_pos "$mem_total"),\"modules\":[$(join_fragments "${mem_fragments[@]}")]}"

# ---------- GPU ----------
gpu_fragments=()

# nvidia-smi, when present, gives exact name / VRAM / driver version.
smi_lines=()
if command -v nvidia-smi >/dev/null 2>&1; then
  while IFS= read -r line; do
    [ -n "$line" ] && smi_lines+=("$line")
  done <<EOF
$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>/dev/null)
EOF
fi

gpu_from_smi() { # $1 = index among NVIDIA entries -> "name|vramBytes|driverVersion"
  local line name mib ver
  line="${smi_lines[$1]:-}"
  [ -n "$line" ] || return
  name="$(trim "$(printf '%s' "$line" | cut -d, -f1)")"
  mib="$(trim "$(printf '%s' "$line" | cut -d, -f2)")"
  ver="$(trim "$(printf '%s' "$line" | cut -d, -f3)")"
  local vram=""
  case "$mib" in '' | *[!0-9]*) ;; *) vram=$((mib * 1048576)) ;; esac
  printf '%s|%s|%s' "$name" "$vram" "$ver"
}

if command -v lspci >/dev/null 2>&1; then
  nv_idx=0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    slot="$(printf '%s' "$line" | awk '{print $1}')"
    desc="$line"
    case "$desc" in
      *"controller: "*) desc="${desc#*controller: }" ;;
      *) desc="${desc#*: }" ;;
    esac
    desc="$(trim "${desc% (rev *}")"
    gname=""
    case "$desc" in
      *"["*"]"*)
        bracket="$(printf '%s' "$desc" | sed -n 's/.*\[\(.*\)\].*/\1/p')"
        vendor_word="$(printf '%s' "$desc" | awk '{print $1}')"
        case "$bracket" in
          "$vendor_word"*) gname="$bracket" ;;
          *) gname="$vendor_word $bracket" ;;
        esac
        ;;
      *) gname="$desc" ;;
    esac
    # VRAM via the DRM node for this PCI slot (exact on amdgpu).
    gvram=""
    for card in /sys/class/drm/card[0-9]*; do
      [ -e "$card/device" ] || continue
      target="$(readlink -f "$card/device" 2>/dev/null)"
      case "$target" in
        *"$slot")
          v="$(trim "$(read_file "$card/device/mem_info_vram_total")")"
          case "$v" in '' | *[!0-9]*) ;; *) gvram="$v" ;; esac
          ;;
      esac
    done
    # Driver version: a module version when the kernel exposes one.
    gver=""
    drv="$(lspci -k -s "$slot" 2>/dev/null | awk -F: '/Kernel driver in use/{v=$2; sub(/^[ \t]+/, "", v); print v; exit}')"
    if [ -n "$drv" ]; then
      gver="$(trim "$(read_file "/sys/module/$drv/version")")"
    fi
    case "$desc" in
      *NVIDIA* | *nvidia*)
        if [ "${#smi_lines[@]}" -gt 0 ]; then
          smi_data="$(gpu_from_smi "$nv_idx")"
          if [ -n "$smi_data" ]; then
            s_name="${smi_data%%|*}"; rest="${smi_data#*|}"
            s_vram="${rest%%|*}"; s_ver="${rest#*|}"
            [ -n "$s_name" ] && gname="$s_name"
            [ -n "$s_vram" ] && gvram="$s_vram"
            [ -n "$s_ver" ] && gver="$s_ver"
          fi
        fi
        nv_idx=$((nv_idx + 1))
        ;;
    esac
    gpu_fragments+=("{\"name\":$(jstr_plain "$gname"),\"vramBytes\":$(jnum_pos "$gvram"),\"driverVersion\":$(jstr_plain "$gver")}")
  done <<EOF
$(lspci 2>/dev/null | grep -E 'VGA compatible controller|3D controller|Display controller')
EOF
fi

if [ "${#gpu_fragments[@]}" -eq 0 ]; then
  # DRM-only fallback: a GPU exists but its model name is not exposed
  # without lspci, so the name honestly stays null.
  for card in /sys/class/drm/card[0-9]*; do
    [ -e "$card/device/vendor" ] || continue
    v="$(trim "$(read_file "$card/device/mem_info_vram_total")")"
    drv_link="$(readlink "$card/device/driver" 2>/dev/null)"
    drv_name="$(basename "$drv_link" 2>/dev/null)"
    ver=""
    if [ -n "$drv_name" ]; then ver="$(trim "$(read_file "/sys/module/$drv_name/version")")"; fi
    gpu_fragments+=("{\"name\":null,\"vramBytes\":$(jnum_pos "$v"),\"driverVersion\":$(jstr_plain "$ver")}")
  done
fi

if [ "${#gpu_fragments[@]}" -eq 0 ] && [ "${#smi_lines[@]}" -gt 0 ]; then
  i=0
  while [ "$i" -lt "${#smi_lines[@]}" ]; do
    smi_data="$(gpu_from_smi "$i")"
    s_name="${smi_data%%|*}"; rest="${smi_data#*|}"
    s_vram="${rest%%|*}"; s_ver="${rest#*|}"
    gpu_fragments+=("{\"name\":$(jstr_plain "$s_name"),\"vramBytes\":$(jnum_pos "$s_vram"),\"driverVersion\":$(jstr_plain "$s_ver")}")
    i=$((i + 1))
  done
fi
gpus_json="[$(join_fragments "${gpu_fragments[@]}")]"

# ---------- Motherboard / BIOS ----------
mb_manufacturer="$(read_file "$DMI_DIR/board_vendor")"
mb_product="$(read_file "$DMI_DIR/board_name")"
mb_bios_version="$(trim "$(read_file "$DMI_DIR/bios_version")")"
if [ "$mb_bios_version" = "0" ]; then mb_bios_version=""; fi # placeholder, not a version
mb_bios_date_raw="$(trim "$(read_file "$DMI_DIR/bios_date")")"
mb_bios_date="$mb_bios_date_raw"
case "$mb_bios_date_raw" in
  [0-9][0-9]/[0-9][0-9]/[0-9][0-9][0-9][0-9])
    # sysfs reports MM/DD/YYYY; the schema uses YYYY-MM-DD like collect.ps1.
    mm="${mb_bios_date_raw%%/*}"; rest="${mb_bios_date_raw#*/}"
    dd="${rest%%/*}"; yyyy="${rest##*/}"
    mb_bios_date="$yyyy-$mm-$dd"
    ;;
esac
motherboard_json="{\"manufacturer\":$(jstr "$mb_manufacturer"),\"product\":$(jstr "$mb_product"),\"biosVersion\":$(jstr "$mb_bios_version"),\"biosDate\":$(jstr_plain "$mb_bios_date")}"

# ---------- Storage ----------
phys_fragments=()
if command -v lsblk >/dev/null 2>&1; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    get_pair() {
      local key="$1" v=""
      case "$line" in
        *"$key=\""*)
          v="${line#*"$key=\""}"
          v="${v%%\"*}"
          ;;
      esac
      printf '%s' "$v"
    }
    d_type="$(get_pair TYPE)"
    [ "$d_type" = "disk" ] || continue
    d_name="$(get_pair NAME)"
    case "$d_name" in loop*) continue ;; esac
    d_model="$(get_pair MODEL)"
    if [ -z "$(trim "$d_model")" ]; then
      d_model="$(read_file "/sys/class/block/$d_name/device/model")"
    fi
    d_size="$(get_pair SIZE)"
    d_tran="$(get_pair TRAN)"
    d_rota="$(get_pair ROTA)"
    if [ -z "$(trim "$d_tran")" ]; then
      devpath="$(readlink -f "/sys/class/block/$d_name" 2>/dev/null)"
      case "$devpath" in
        *nvme*) d_tran="nvme" ;;
        *"/ata"*) d_tran="sata" ;;
        *usb*) d_tran="usb" ;;
        *virtio*) d_tran="virtio" ;;
      esac
    fi
    case "$(printf '%s' "$d_tran" | tr 'A-Z' 'a-z')" in
      nvme) bus_json='"NVMe"' ;;
      sata) bus_json='"SATA"' ;;
      sas) bus_json='"SAS"' ;;
      scsi) bus_json='"SCSI"' ;;
      usb) bus_json='"USB"' ;;
      ata) bus_json='"ATA"' ;;
      virtio) bus_json='"VirtIO"' ;;
      mmc) bus_json='"MMC"' ;;
      "") bus_json='null' ;;
      *) bus_json="$(jstr_plain "$(printf '%s' "$d_tran" | tr 'a-z' 'A-Z')")" ;;
    esac
    case "$d_rota" in
      1) media_json='"HDD"' ;;
      0) media_json='"SSD"' ;;
      *) media_json='null' ;;
    esac
    phys_fragments+=("{\"model\":$(jstr "$d_model"),\"sizeBytes\":$(jnum_pos "$d_size"),\"mediaType\":$media_json,\"busType\":$bus_json}")
  done <<EOF
$(lsblk -b -d -n -P -o NAME,MODEL,SIZE,TRAN,ROTA,TYPE 2>/dev/null)
EOF
else
  for blk in /sys/class/block/*; do
    [ -e "$blk/size" ] || continue
    bname="$(basename "$blk")"
    case "$bname" in loop* | ram* | dm-* | sr*) continue ;; esac
    sectors="$(trim "$(read_file "$blk/size")")"
    case "$sectors" in '' | *[!0-9]*) continue ;; esac
    lbs="$(trim "$(read_file "$blk/queue/logical_block_size")")"
    case "$lbs" in '' | *[!0-9]*) lbs=512 ;; esac
    bsize=$((sectors * lbs))
    bmodel="$(read_file "$blk/device/model")"
    brota="$(trim "$(read_file "$blk/queue/rotational")")"
    case "$brota" in 1) media_json='"HDD"' ;; 0) media_json='"SSD"' ;; *) media_json='null' ;; esac
    devpath="$(readlink -f "$blk" 2>/dev/null)"
    bus_json='null'
    case "$devpath" in
      *nvme*) bus_json='"NVMe"' ;;
      *"/ata"*) bus_json='"SATA"' ;;
      *usb*) bus_json='"USB"' ;;
      *virtio*) bus_json='"VirtIO"' ;;
    esac
    phys_fragments+=("{\"model\":$(jstr "$bmodel"),\"sizeBytes\":$(jnum_pos "$bsize"),\"mediaType\":$media_json,\"busType\":$bus_json}")
  done
fi

log_fragments=()
seen_mounts=""
while IFS= read -r line; do
  [ -n "$line" ] || continue
  # df -B1 -PT -P columns: source type total used avail capacity mountpoint...
  set -- $line
  [ "$#" -ge 7 ] || continue
  l_source="$1"; l_type="$2"; l_total="$3"; l_avail="$5"
  shift 6; l_mount="$*"
  case "$l_type" in
    tmpfs | devtmpfs | proc | sysfs | cgroup | cgroup2 | debugfs | \
    securityfs | pstore | efivarfs | bpf | tracefs | autofs | mqueue | \
    hugetlbfs | fusectl | configfs | ramfs | devpts | selinuxfs | \
    squashfs | nsfs | rpc_pipefs | binfmt_misc) continue ;;
  esac
  case "$l_source" in "" | "none") continue ;; esac
  dedupe_key="$l_source|$l_total"
  case "|$seen_mounts|" in *"|$dedupe_key|"*) continue ;; esac
  seen_mounts="$seen_mounts|$dedupe_key"
  l_label=""
  case "$l_source" in
    /dev/*)
      if command -v lsblk >/dev/null 2>&1; then
        l_label="$(lsblk -n -o LABEL "$l_source" 2>/dev/null | head -n 1)"
      fi
      ;;
  esac
  log_fragments+=("{\"drive\":$(jstr_plain "$l_mount"),\"label\":$(jstr "$l_label"),\"fileSystem\":$(jstr_plain "$l_type"),\"totalBytes\":$(jnum_pos "$l_total"),\"freeBytes\":$(jnum_nonneg "$l_avail")}")
done <<EOF
$(df -B1 -PT -P 2>/dev/null | tail -n +2)
EOF
storage_json="{\"physical\":[$(join_fragments "${phys_fragments[@]}")],\"logical\":[$(join_fragments "${log_fragments[@]}")]}"

# ---------- Network ----------
net_fragments=()
for ndir in /sys/class/net/*; do
  [ -e "$ndir" ] || continue
  iface="$(basename "$ndir")"
  [ "$iface" = "lo" ] && continue # physical adapters only, like collect.ps1
  n_mac_raw="$(trim "$(read_file "$ndir/address")")"
  if [ -z "$n_mac_raw" ] || [ "$n_mac_raw" = "00:00:00:00:00:00" ]; then
    n_mac_json='null'
  else
    n_mac="$(printf '%s' "$n_mac_raw" | tr 'a-f' 'A-F' | tr ':' '-')"
    n_mac_json="$(jstr_plain "$n_mac")"
  fi
  n_status_raw="$(trim "$(read_file "$ndir/operstate")")"
  case "$n_status_raw" in
    up) n_status="Up" ;;
    down | lowerlayerdown) n_status="Disconnected" ;;
    dormant) n_status="Dormant" ;;
    unknown) n_status="Unknown" ;;
    "") n_status="" ;;
    *) n_status="$(printf '%s' "$n_status_raw" | sed 's/^./\U&/')" ;;
  esac
  n_desc=""
  if [ -e "$ndir/device/driver" ]; then
    n_desc="$(basename "$(readlink "$ndir/device/driver" 2>/dev/null)" 2>/dev/null)"
  fi
  if [ -d "$ndir/wireless" ] && [ -n "$n_desc" ]; then
    n_desc="$n_desc (Wireless)"
  elif [ -d "$ndir/wireless" ]; then
    n_desc="Wireless"
  fi
  n_speed="$(trim "$(read_file "$ndir/speed" 2>/dev/null)")"
  ipv4_fragments=()
  ipv6_fragments=()
  if command -v ip >/dev/null 2>&1; then
    while IFS= read -r addr; do
      [ -n "$addr" ] && ipv4_fragments+=("$(jstr_plain "$addr")")
    done <<EOF
$(ip -o -4 addr show dev "$iface" 2>/dev/null | awk '{split($4, a, "/"); print a[1]}')
EOF
    while IFS= read -r addr; do
      [ -n "$addr" ] && ipv6_fragments+=("$(jstr_plain "$addr")")
    done <<EOF
$(ip -o -6 addr show dev "$iface" 2>/dev/null | awk '{split($4, a, "/"); print a[1]}')
EOF
  fi
  net_fragments+=("{\"name\":$(jstr_plain "$iface"),\"description\":$(jstr_plain "$n_desc"),\"status\":$(jstr_plain "$n_status"),\"ipv4\":[$(join_fragments "${ipv4_fragments[@]}")],\"ipv6\":[$(join_fragments "${ipv6_fragments[@]}")],\"macAddress\":$n_mac_json,\"linkSpeedMbps\":$(jnum_pos "$n_speed")}")
done
network_json="[$(join_fragments "${net_fragments[@]}")]"

# ---------- Displays ----------
disp_fragments=()
if [ -n "${DISPLAY:-}" ] && command -v xrandr >/dev/null 2>&1; then
  xr_out="$(xrandr --query 2>/dev/null)"
  cur_name=""
  while IFS= read -r line; do
    case "$line" in
      *" connected "*)
        cur_name="$(printf '%s' "$line" | awk '{print $1}')"
        ;;
      ' '*)
        # Indented mode line; the current mode is marked with '*'.
        case "$line" in
          *"*"*)
            mode_tok="$(printf '%s' "$line" | awk '{print $1}')"
            ref_tok="$(printf '%s' "$line" | awk '{for (i = 2; i <= NF; i++) if ($i ~ /\*/) {print $i; exit}}')"
            dw="${mode_tok%%x*}"; dh="${mode_tok##*x}"
            dref="$(printf '%s' "$ref_tok" | tr -d '*+')"
            dref_int="${dref%%.*}"
            if [ -n "$cur_name" ]; then
              disp_fragments+=("{\"name\":$(jstr_plain "$cur_name"),\"width\":$(jnum_pos "$dw"),\"height\":$(jnum_pos "$dh"),\"refreshRateHz\":$(jnum_pos "$dref_int")}")
              cur_name=""
            fi
            ;;
        esac
        ;;
    esac
  done <<EOF
$xr_out
EOF
fi
if [ "${#disp_fragments[@]}" -eq 0 ]; then
  for conn in /sys/class/drm/card*-*; do
    [ -e "$conn/status" ] || continue
    [ "$(trim "$(read_file "$conn/status")")" = "connected" ] || continue
    first_mode="$(head -n 1 "$conn/modes" 2>/dev/null)"
    first_mode="$(trim "$first_mode")"
    case "$first_mode" in *x*) ;; *) continue ;; esac
    dw="${first_mode%%x*}"; dh="${first_mode##*x}"
    conn_name="$(basename "$conn")"
    conn_name="${conn_name#card[0-9]*-}"
    disp_fragments+=("{\"name\":$(jstr_plain "$conn_name"),\"width\":$(jnum_pos "$dw"),\"height\":$(jnum_pos "$dh"),\"refreshRateHz\":null}")
  done
fi
displays_json="[$(join_fragments "${disp_fragments[@]}")]"

# ---------- Battery ----------
battery_json='null'
for ps in /sys/class/power_supply/*; do
  [ -d "$ps" ] || continue
  [ "$(trim "$(read_file "$ps/type")")" = "Battery" ] || continue
  b_capacity="$(trim "$(read_file "$ps/capacity")")"
  b_status="$(read_file "$ps/status")"
  b_design=""
  e_design="$(trim "$(read_file "$ps/energy_full_design")")"
  case "$e_design" in
    '' | *[!0-9]*) ;;
    *) b_design=$((e_design / 1000)) ;;
  esac
  if [ -z "$b_design" ]; then
    c_design="$(trim "$(read_file "$ps/charge_full_design")")"
    v_design="$(trim "$(read_file "$ps/voltage_min_design")")"
    case "$c_design" in
      '' | *[!0-9]*) ;;
      *)
        case "$v_design" in
          '' | *[!0-9]*) ;;
          *) b_design=$((c_design * v_design / 1000000000)) ;;
        esac
        ;;
    esac
  fi
  b_full=""
  e_full="$(trim "$(read_file "$ps/energy_full")")"
  case "$e_full" in
    '' | *[!0-9]*) ;;
    *) b_full=$((e_full / 1000)) ;;
  esac
  if [ -z "$b_full" ]; then
    c_full="$(trim "$(read_file "$ps/charge_full")")"
    v_now="$(trim "$(read_file "$ps/voltage_now")")"
    if [ -z "$v_now" ]; then v_now="$(trim "$(read_file "$ps/voltage_min_design")")"; fi
    case "$c_full" in
      '' | *[!0-9]*) ;;
      *)
        case "$v_now" in
          '' | *[!0-9]*) ;;
          *) b_full=$((c_full * v_now / 1000000000)) ;;
        esac
        ;;
    esac
  fi
  battery_json="{\"chargePercent\":$(jnum_nonneg "$b_capacity"),\"status\":$(jstr_plain "$b_status"),\"designCapacityMWh\":$(jnum_pos "$b_design"),\"fullChargeCapacityMWh\":$(jnum_pos "$b_full")}"
  break
done

# ---------- USB / peripherals ----------
peri_fragments=()
for dev in /sys/bus/usb/devices/*; do
  [ -e "$dev/idVendor" ] || continue
  d_base="$(basename "$dev")"
  case "$d_base" in *":"*) continue ;; esac # interface entries, not devices
  d_vendor="$(trim "$(read_file "$dev/idVendor")")"
  [ "$d_vendor" = "1d6b" ] && continue # Linux Foundation root hubs are internal
  d_product="$(read_file "$dev/product")"
  d_maker="$(read_file "$dev/manufacturer")"
  d_idproduct="$(trim "$(read_file "$dev/idProduct")")"
  if [ -n "$(trim "$d_product")" ]; then
    p_name="$d_product"
  elif [ -n "$d_vendor" ]; then
    p_name="USB Device $d_vendor:$d_idproduct"
  else
    p_name=""
  fi
  d_class="$(trim "$(read_file "$dev/bDeviceClass")")"
  p_desc=""
  case "$d_class" in
    01) p_desc="USB Audio Device" ;;
    02) p_desc="USB Communications Device" ;;
    03) p_desc="USB Input Device" ;;
    08) p_desc="USB Mass Storage Device" ;;
    09) p_desc="USB Hub" ;;
    0b) p_desc="USB Smart Card Reader" ;;
    0d) p_desc="USB Content Security Device" ;;
    0e) p_desc="USB Video Device" ;;
    0f) p_desc="USB Personal Healthcare Device" ;;
    dc) p_desc="USB Diagnostic Device" ;;
    e0) p_desc="USB Wireless Controller" ;;
    ef) p_desc="USB Miscellaneous Device" ;;
    fe) p_desc="USB Application Specific Device" ;;
    ff) p_desc="USB Vendor Specific Device" ;;
    *) p_desc="$(trim "$d_maker")" ;;
  esac
  if [ -z "$(trim "$p_name")" ]; then continue; fi
  peri_fragments+=("{\"name\":$(jstr_plain "$p_name"),\"description\":$(jstr_plain "$p_desc")}")
done
peripherals_json="[$(join_fragments "${peri_fragments[@]}")]"

# ---------- Assemble & write ----------
collected_at="$(date -Iseconds 2>/dev/null)"
if [ -z "$collected_at" ]; then
  collected_at="$(date +"%Y-%m-%dT%H:%M:%S%z" 2>/dev/null | sed 's/\([+-][0-9][0-9]\)\([0-9][0-9]\)$/\1:\2/')"
fi

report="{\"format\":\"moni-report\",\"version\":1,\"collectedAt\":$(jstr_plain "$collected_at"),\"collector\":\"Moni collect.sh 1.0.0\",\"sampleData\":false,\"system\":$system_json,\"cpu\":$cpu_json,\"memory\":$memory_json,\"gpus\":$gpus_json,\"motherboard\":$motherboard_json,\"storage\":$storage_json,\"network\":$network_json,\"displays\":$displays_json,\"battery\":$battery_json,\"peripherals\":$peripherals_json}"

printf '%s\n' "$report" > "$OUT_PATH"

echo ''
echo "完了しました: $OUT_PATH"
echo 'このファイルを Moni の index.html で開くと、デバイス情報を確認できます。'
echo '情報はこの PC の中だけに保存され、外部へ送信されることはありません。'
