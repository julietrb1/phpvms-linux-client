-- FlyWithLua UDP bridge for phpVMS Python client
-- Drop this file into X-Plane 12 Resources/plugins/FlyWithLua/Scripts/
-- Requires LuaSocket (bundled with FlyWithLua NG) and a JSON library (dkjson or cjson).

-- =====================
-- User configuration
-- =====================
local HOST = "10.0.0.132"
local PORT = 47777         -- must match the Python client's UDP bridge port
local SEND_INTERVAL = 0.5  -- minimum seconds between sends (coarse throttle)

-- =====================
-- Libraries
-- =====================
local socket = require("socket")
local udp = socket.udp()
udp:settimeout(0)
udp:setpeername(HOST, PORT)

-- JSON helper: try dkjson, then cjson; if missing, use a minimal built-in encoder
local json = nil
local ok, lib = pcall(require, "dkjson")
if ok then json = lib end
if not json then
  ok, lib = pcall(require, "cjson")
  if ok then
    json = {
      encode = lib.encode,
      decode = lib.decode,
    }
  end
end

if not json then
  -- Minimal JSON encoder (encode only), suitable for our payloads
  local function escape_str(s)
    s = tostring(s)
    s = s:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\t", "\\t")
    return '"' .. s .. '"'
  end
  local function is_array(t)
    if type(t) ~= 'table' then return false end
    local max = 0
    local count = 0
    for k, _ in pairs(t) do
      if type(k) ~= 'number' then return false end
      if k > max then max = k end
      count = count + 1
    end
    return max == count
  end
  local function encode_value(v)
    local tv = type(v)
    if v == nil then return 'null' end
    if tv == 'number' then return tostring(v) end
    if tv == 'boolean' then return v and 'true' or 'false' end
    if tv == 'string' then return escape_str(v) end
    if tv == 'table' then
      if is_array(v) then
        local parts = {}
        for i = 1, #v do parts[#parts+1] = encode_value(v[i]) end
        return '[' .. table.concat(parts, ',') .. ']'
      else
        local parts = {}
        for k, val in pairs(v) do
          if type(k) == 'string' then
            parts[#parts+1] = escape_str(k) .. ':' .. encode_value(val)
          end
        end
        return '{' .. table.concat(parts, ',') .. '}'
      end
    end
    return 'null'
  end
  json = { encode = encode_value }
  logMsg("[phpVMS UDP] No JSON library found (dkjson or cjson) — using built-in minimal encoder")
end

-- =====================
-- Datarefs
-- =====================
-- Position
dataref("gs_ms", "sim/flightmodel/position/groundspeed", "readonly")     -- m/s
dataref("on_ground", "sim/flightmodel/failures/onground_any", "readonly")
dataref("eng1_running", "sim/flightmodel/engine/ENGN_running", "readonly", 0)
dataref("paused", "sim/time/paused", "readonly")
dataref("radalt_ft", "sim/cockpit2/gauges/indicators/radio_altimeter_height_ft_pilot", "readonly")
dataref("dist_m", "sim/flightmodel/controls/dist", "readonly")
dataref("fuel_1", "sim/cockpit2/fuel/fuel_quantity", "readonly", 0)
dataref("fuel_2", "sim/cockpit2/fuel/fuel_quantity", "readonly", 1)
dataref("fuel_3", "sim/cockpit2/fuel/fuel_quantity", "readonly", 2)
dataref("fuel_4", "sim/cockpit2/fuel/fuel_quantity", "readonly", 3)
dataref("flight_time_sec", "sim/time/total_flight_time_sec", "readonly", 3)
dataref("trk_mag", "sim/flightmodel/position/hpath", "readonly")
dataref("ias", "sim/flightmodel/position/indicated_airspeed", "readonly")
dataref("vs_ms", "sim/flightmodel/position/vh_ind", "readonly")
dataref("alt_agl_m", "sim/flightmodel/position/y_agl", "readonly")

-- =====================
-- Helpers
-- =====================
local last_sent = 0

local function knots(ms)
  return (ms or 0) * 1.94384
end

local function feet(m)
  return (m or 0) * 3.28084
end

local function nautical_miles(metres)
    return (metres or 0) / 1852
end

local function fpm(ms)
    return (ms or 0) * 196.85
end

local status = ""
local timer_start = -1
local final_time_sec = 0
local distance_start = -1
local final_distance = 0

local function calculate_minutes()
    if timer_start == -1 then return 0 end
    return math.floor((flight_time_sec - timer_start) / 60)
end

local function calculate_distance()
    if distance_start == -1 then return 0 end
    return math.floor(nautical_miles(dist_m - distance_start))
end

-- INITIATED = 'INI';
-- SCHEDULED = 'SCH';
-- BOARDING = 'BST';
-- RDY_START = 'RDT';
-- PUSHBACK_TOW = 'PBT';
-- DEPARTED = 'OFB'; // Off block
-- RDY_DEICE = 'DIR';
-- STRT_DEICE = 'DIC';
-- GRND_RTRN = 'GRT'; // Ground return
-- TAXI = 'TXI'; // Taxi
-- TAKEOFF = 'TOF';
-- INIT_CLIM = 'ICL'; // NOT VALID!
-- AIRBORNE = 'TKO';
-- ENROUTE = 'ENR';
-- DIVERTED = 'DV';
-- APPROACH = 'TEN';
-- APPROACH_ICAO = 'APR';
-- ON_FINAL = 'FIN';
-- LANDING = 'LDG';
-- LANDED = 'LAN';
-- ON_BLOCK = 'ONB'; // NOT VALID!
-- ARRIVED = 'ARR';
-- CANCELLED = 'DX';
-- EMERG_DESCENT = 'EMG';
-- PAUSED = 'PSD';

local function detect_status()
    if internal_status == "" or status == "" then
        timer_start = 0
        final_time_sec = 0
        distance_start = 0
        final_distance = 0
      if on_ground == 1 and eng1_running == 0 then
          return "BST"
      elseif on_ground == 1 and eng1_running == 1 then
          return "TXI"
      elseif on_ground == 0 and alt_agl_m > 100 then
          return "ENR"
      end
    end


    if status == "BST" and on_ground == 1 and eng1_running == 1 then
        return "TXI"
    elseif status == "TXI" and on_ground == 1 and ias > 50 then
        timer_start = flight_time_sec
        final_time_sec = 0
        distance_start = dist_m
        final_distance = 0
        return "TOF"
    elseif (status == "TOF" or status == "LDG" or status == "LDG") and on_ground == 0 and alt_agl_m > 100 and vs_ms > 10 then
        return "ENR"
    elseif status == "ENR" and alt_agl_m < 1829 and vs_ms < -5 then -- 6,000 ft AGL
        return "TEN"
    elseif status == "TEN" and alt_agl_m < 305 and vs_ms < -5 then -- 1,000 ft AGL
        return "FIN"
    elseif (status == "TEN" or status == "FIN" or status == "ENR") and on_ground == 0 and alt_agl_m < 46 and vs_ms < -1 then -- 150 ft AGL
        return "LDG"
    elseif status == "LDG" and on_ground == 1 and gs_ms < 5 and alt_agl_m < 10 then
        return "LAN"
    elseif status == "LAN" and on_ground == 1 and gs_ms < 1 then
        final_time_sec = calculate_minutes()
        final_distance = calculate_distance()
        return "ARR"
    elseif status == "ARR" and eng1_running == 0 then
        return "BST"
    end

    return status
end

local function osTimeToISO8601Zulu(timestamp)
    return os.date("!%Y-%m-%dT%H:%M:%SZ", timestamp)
end

local function build_payload()
  status = detect_status()

  local payload = {
    status = paused == 1 and "PSD" or status,
    position = {
      lat = LATITUDE,
      lon = LONGITUDE,
      altitude_msl = math.ceil(feet(ELEVATION)),
      altitude_agl = math.max(0, math.ceil(feet(alt_agl_m))),
      gs = math.floor(knots(gs_ms)),
      sim_time = osTimeToISO8601Zulu(os.time()),
      distance = final_distance ~= 0 and final_distance or calculate_distance(),
      heading = math.floor(trk_mag),
      ias = math.max(0, math.floor(ias)),
      vs = math.floor(fpm(vs_ms)),
    },
    fuel = math.floor(fuel_1 + fuel_2 + fuel_3 + fuel_4),
    flight_time = final_time_sec ~= 0 and final_time_sec or calculate_minutes(),
  }
  return payload
end

local function send_payload()
  if not json then return end
  local t = os.time()
  if (t - last_sent) < SEND_INTERVAL then return end
  last_sent = t
  local body = json.encode(build_payload())
  udp:send(body)
end

function phpvms_udp_loop()
  send_payload()
end

do_sometimes("phpvms_udp_loop()")
