-- FlyWithLua UDP bridge for phpVMS Python client
-- Drop this file into X-Plane 12 Resources/plugins/FlyWithLua/Scripts/
-- Requires LuaSocket (bundled with FlyWithLua NG) and a JSON library (dkjson or cjson).

-- =====================
-- User configuration
-- =====================
local HOST = "127.0.0.1"
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
dataref("alt_agl", "sim/flightmodel/position/y_agl", "readonly")

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

local current_status = "BOARDING"
local timer_start = 0

local function detect_status()
    if paused == 1 then
        return "PSD"
    end

    if current_status == "BOARDING" and on_ground == 1 and eng1_running == 0 and gs_ms < 1 and alt_agl < 10 then
        current_status = "RDY_START"
        return "BST"
    elseif current_status == "RDY_START" and on_ground == 1 and eng1_running == 1 and gs_ms < 1 then
        current_status = "DEPARTED"
        timer_start = os.clock()
        return "TXI"
    elseif current_status == "DEPARTED" and on_ground == 1 and gs_ms > 5 and (os.clock() - timer_start >= 5 or timer_start == 0) then
        current_status = "TAXI"
        timer_start = 0
        return "TXI"
    elseif current_status == "TAXI" and on_ground == 1 and gs_ms > 5 and ias > 10 then
        -- No change in return; wait for next condition
    elseif current_status == "TAXI" and on_ground == 1 and ias > 50 and vs_ms > 5 then
        current_status = "TAKEOFF"
        return "TOF"
    elseif current_status == "TAKEOFF" and on_ground == 0 and alt_agl > 100 and vs_ms > 10 then
        current_status = "AIRBORNE"
        if on_ground == 0 and alt_agl > 1000 and gs_ms > 50 then  -- Check for ENROUTE skip
            current_status = "ENROUTE"
            return "ENR"
        end
        return "ENR"
    elseif current_status == "ENROUTE" and on_ground == 0 and alt_agl < 5000 and vs_ms < -5 and radalt_ft < 2000 then
        current_status = "APPROACH"
        -- No direct return; fall through
    elseif current_status == "APPROACH" and on_ground == 0 and alt_agl < 100 and vs_ms < -1 and radalt_ft < 50 then
        current_status = "LANDING"
        return "TOF"
    elseif current_status == "LANDING" and on_ground == 1 and gs_ms < 5 and alt_agl < 10 then
        current_status = "LANDED"
        timer_start = os.clock()
        return "ARR"
    elseif current_status == "LANDED" and on_ground == 1 and gs_ms < 1 and (os.clock() - timer_start >= 10 or timer_start == 0) then
        current_status = "ON_BLOCK"
        return "ARR"
    elseif current_status == "ON_BLOCK" and on_ground == 1 and gs_ms < 1 and flight_time_sec > 60 then
        current_status = "ARRIVED"
        return "ARR"
    end

    -- Fallback: Return the last status or handle unmapped cases
    print("Warning: phpVMS status fallback. current_status:" .. current_status .. ", on_ground:" .. on_ground .. ", eng1_running:" .. eng1_running .. ", gs_ms:" .. gs_ms .. ", alt_agl" .. alt_agl)
    if eng1_running == 1 then
        print("ENG RUNNING")
    else
        print("ENG NOT RUNNING")
    end

    if alt_agl < 1 then
        print("ALT AGL low")
    else
        print("ALT AGL high")
    end

    if on_ground == 1 then
        print("ON GND")
    else
        print("NOT ON GND")
    end

    if gs_ms < 1 then
        print("GS low")
    else
        print("GS high")
    end

    if on_ground == 1 and gs_ms < 1 then
        return "ARR"
    elseif on_ground == 1 and gs_ms >= 1.5 then
        return "TXI"
    elseif on_ground == 0 and radalt_ft < 100 then
        return "TOF"
    elseif on_ground == 0 and radalt_ft >= 100 then
        return "ENR"
    end

    return current_status
end


local function osTimeToISO8601Zulu(timestamp)
    return os.date("!%Y-%m-%dT%H:%M:%SZ", timestamp)
end

local function build_payload()
  local status = detect_status()
  print("Detected " .. status)
  local payload = {
    status = status,
    position = {
      lat = LATITUDE,
      lon = LONGITUDE,
      altitude_msl = math.ceil(feet(ELEVATION)),
      altitude_agl = math.max(0, math.ceil(feet(alt_agl))),
      gs = math.floor(knots(gs_ms)),
      sim_time = osTimeToISO8601Zulu(os.time()),
      distance = math.floor(nautical_miles(dist_m)),
      heading = math.floor(trk_mag),
      ias = math.max(0, math.floor(ias)),
      vs = math.floor(fpm(vs_ms)),
    },
    fuel = math.floor(fuel_1 + fuel_2 + fuel_3 + fuel_4),
    flight_time = math.floor(flight_time_sec / 60),
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
