; Orva batch test: startup, leveling memory, center routing, pivots,
; flow test outline, wipe, overhang guard, tower reattach.
ORVA_STARTUP
ORVA_LEVEL_STATUS
ORVA_MOTION_STATUS
G90
M83
G1 Z5 F600
; through center within reach (arm ends behind center)
G1 X40 Y0 F6000
G1 X-20 Y0
ORVA_MOTION_STATUS
; then far away: arm must come back through center first
G1 X70 Y30
; full-diameter printing line: pivot at center
G1 Z0.3
G1 X80 Y0
G1 X-80 Y0 E5
ORVA_MOTION_STATUS
; line passing 0.1 mm from center (snapped through it)
G1 X60 Y0.1
G1 X-10 Y-0.05 E2
; general moves around the bed, some near center
G1 X50 Y50 E2
G1 X-50 Y50 E2
G1 X5 Y-3 E1
G1 X-60 Y-40 E2
G1 Z5
; second leveling run adds to memory
ORVA_RELEVEL
ORVA_LEVEL_STATUS
; slicer-style object + flow test + wipe
EXCLUDE_OBJECT_DEFINE NAME=part1 CENTER=105,0 POLYGON=[[97,-8],[113,-8],[113,8],[97,8]]
ORVA_WIPER_MODE MODE=AUTO
ORVA_FLOW_TEST
ORVA_WIPE
; overhang object -> wiper overhang mode
EXCLUDE_OBJECT_DEFINE NAME=bowl CENTER=0,110 POLYGON=[[-25,100],[25,100],[25,140],[-25,140]]
ORVA_WIPER_MODE MODE=AUTO
ORVA_WIPE
; tower off and on again -> re-level
ORVA_TOWER STATE=DETACHED
ORVA_TOWER STATE=ATTACHED
ORVA_LEVEL_STATUS
G1 Z10
M400
