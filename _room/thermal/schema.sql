-- Thermal camera minutes, written only by the room edge function (action "thermal", key labelled "thermal camera").
-- Applied as migration "room_thermal". Temperatures are °C, calibrated against the desk thermometer.
create table if not exists public.room_thermal (
  ts timestamptz primary key default now(),
  window_c numeric,          -- window glass (or the blind, when it's down)
  unit_c numeric,            -- front of the heat/AC unit under the window
  unit_state text,           -- heating / cooling / off, from the unit against the walls
  unit_leak boolean,         -- off but colder than the wall around it: outside air coming through
  walls_c numeric,           -- median of the walls, closet and ceiling the camera sees (what your body radiates to)
  floor_c numeric,
  floor_min_c numeric,       -- coldest 5% of the floor
  bed_c numeric,
  head_c numeric,            -- warmest spot on the bed
  in_bed boolean,
  people_px integer,         -- pixels at body temperature, outside the PC, unit and lamps
  stats jsonb not null default '{}'::jsonb,   -- the full summary, including calibration
  frame jsonb                -- every 15 min: {w: 80, h: 62, dc_i16_b64}: little-endian int16 tenths of a °C, row by row
);
alter table public.room_thermal enable row level security;   -- no policies: only the service role (the edge function) touches it
comment on table public.room_thermal is 'Room Coach thermal camera, one row a minute from the PC agent (_room/thermal).';
