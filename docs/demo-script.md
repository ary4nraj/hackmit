# Two-minute demo

Be explicit: current dashboard demo is a simulator using real persistent memory and real control logic.

1. Start `make run`, open localhost:8000. The initial view observes backpack at entrance table.
2. Ask “Where is my backpack?” Show last-seen age/confidence and SQLite-backed evidence.
3. Click “Demo: move backpack to back wall”. Ground truth changes; memory does not.
4. Ask “Find my backpack”. Show old-zone inspection, INVALIDATED, bounded waypoints, rediscovery,
   MOVED entrance table → back wall. Explain that the finding came from observation after movement.
5. Ask “What changed?” Show the same evidence-backed change in the timeline.
6. Ask “Find the package and then check whether anyone is near the door.” The package/person seeded
   at entrance will only enter memory when that view is inspected.
7. Start investigation and press STOP. It latches; Resume is required before further motion.

For an independent automated run: `make demo` (in-memory database, deterministic).
Real camera side demo: `python -m scripts.test_camera --frames 10`; show stored detection evidence.
Do not claim simulated movement is Go2 movement, or laptop CPU inference is GX10 inference.
When live Go2 is commissioned, replace the mock relocation button with a teammate moving the object.

## Real-camera variant (no Go2 required)

`make run-webcam` with the laptop or a USB camera pointed at a table. Frame thirds are the zones.
1. Place the backpack on the left third; wait for the KNOWN CURRENT card ("camera left").
2. Move it to the right third while saying "the world changed, memory did not".
3. Ask "Where is my backpack now?" → the investigator re-inspects, appearance links the sighting,
   timeline shows `MOVED camera left → camera right [matched by appearance 0.9x]`.
4. Hide it entirely and ask again → INVALIDATED + DISAPPEARED, answer says it was not observed.
5. Ask "What changed?".
Say plainly that this is a stationary camera; the Go2 replaces "image third" with surveyed waypoints.
