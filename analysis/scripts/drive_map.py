#!/usr/bin/env python3
"""Drive the built map in a browser and check what only a browser can answer.

**This is not the test suite and does not overlap with it.** ``pytest`` asserts
on the page's *source*: it can prove the template says ``metresPerPixel``, that a
handler is registered, that a selector is named. It cannot prove that the drawn
angle is the ground's angle, that a wheel over the curve leaves the map's zoom
alone, that a disc is not clipped in half, or that two controls do not cover each
other. Every defect found on this panel in a week was invisible to the source
tests and visible in thirty seconds of driving.

Two kinds of reading, and the difference is the whole design:

``holds``
    A structural invariant. It does not move when the data moves — both axes
    carrying one scale, a mark lying on its line, two panels not overlapping.
    A red one is a defect.

``stands``
    A figure recorded from a build. It moves when the sources move, legitimately:
    a re-export of Turrutebasen changes how many paths the page draws. A red one
    is *news*, and the answer may be to update the number here rather than the
    code — but only after looking at why.

Run it with ``command make drive``. It needs a built page and about a minute:
loading 39.6 MB of HTML is 25 s of that, which is why everything runs in one
browser session rather than one apiece.

The script exits **1** where an invariant broke and **2** where only a recorded
figure moved. ``make`` turns any failed recipe into its own exit 2 and swallows
that distinction, so read it off the last line of the report rather than off the
shell — or run the script directly.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

#: The page this drives. Built by ``command make map``.
PAGE = pathlib.Path("analysis/output/lomsdal-visten.html")

#: A chain long enough that the panel draws it coarser than its own samples, so
#: there is something to zoom into. **A chain id is not a durable reference** —
#: the notes say so about checksums and names alike — so it lives here, once,
#: and the checks that need it say they were skipped rather than passing when it
#: is gone. Any chain over about 20 km will do.
LONG_CHAIN = "trail-group-ut-no-414306-7244296-42442"

#: How long to wait after ``goto`` before believing anything. The page decodes a
#: 4.93 MB payload into a graph on load.
SETTLE_MS = 20_000


@dataclass
class Reading:
    """One thing measured, and what it was measured against."""

    what: str
    got: Any
    want: Any
    #: Absolute tolerance for a number. Zero means exactly.
    within: float = 0.0
    #: True for a structural invariant, False for a figure recorded from a build.
    holds: bool = True
    note: str = ""

    @property
    def passed(self) -> bool:
        """Whether the measurement matches what it was measured against."""
        if isinstance(self.want, bool) or isinstance(self.got, bool):
            return bool(self.got) == bool(self.want)
        if isinstance(self.want, int | float) and isinstance(self.got, int | float):
            return abs(float(self.got) - float(self.want)) <= self.within
        return bool(self.got == self.want)


@dataclass
class Check:
    """A named group of readings, and whether it could run at all."""

    name: str
    readings: list[Reading] = field(default_factory=list)
    skipped: str = ""


# ---------------------------------------------------------------------------
# What the page is asked, in the page's own language.
# ---------------------------------------------------------------------------

MAP_OBJECT = "window[Object.keys(window).find(k => k.startsWith('map_'))]"


def with_map(js: str) -> str:
    """Put the map object into a snippet.

    Args:
        js: A snippet naming the map as ``__MAP__``

    Returns:
        The snippet, ready to evaluate
    """
    return js.replace("__MAP__", MAP_OBJECT)


SELECT_CHAIN = with_map("""(cls) => {
  const map = __MAP__;
  let found = null;
  const walk = layer => { if (found) return;
    if (layer.options && layer.options.className === cls) { found = layer; return; }
    if (layer.eachLayer) layer.eachLayer(walk); };
  map.eachLayer(walk);
  if (!found) { return false; }
  found.fire('click');
  // Firing a layer's click opens its popup as well, and a popup auto-pans to
  // the middle of the map and swallows the wheel. Closing it here is what keeps
  // the wheel checks below measuring the map instead of the popup.
  if (found.closePopup) { found.closePopup(); }
  // Since the chrome, a popup does not float at all: it is taken into the
  // detail panel, which on a narrow screen covers the map by design. Every
  // check below this one is about the map, so the panel is put away here and
  // the chrome has a check of its own.
  if (window.trailsChrome) { window.trailsChrome.close(); }
  return true; }""")

FURNITURE = with_map("""() => {
  const paths = [...document.querySelectorAll('.leaflet-overlay-pane path')];
  // The legend and the base-map picker are panels the chrome owns now, so they
  // are addressed by their own names rather than by the corner they used to
  // stand in. They are in the document whether or not anybody has them open --
  // hidden, not detached, because a control that measures zero caps itself
  // against nothing.
  const legend = [...document.querySelectorAll('.trails-legend input')];
  const bases = [...document.querySelectorAll('.trails-basemap input')];
  const rail = document.querySelector('.trails-rail');
  const zoom = document.querySelector('.leaflet-control-zoom');
  const at = node => node ? Math.round(node.getBoundingClientRect().left) : null;
  return {
    paths: paths.length,
    // A chain drawn as a line, and a chain drawn as a circle marker: Leaflet
    // draws a CircleMarker as a path of two arcs, and 298 of these chains are
    // short enough to be drawn that way. Both carry a chain class, which is why
    // counting the class alone gives 11,588 and not the 11,290 the decomposition
    // in the notes names.
    lines: paths.filter(p => [...p.classList].some(c => c.indexOf('trail-group-') === 0)
                             && !/a[\\d.]/i.test(p.getAttribute('d') || '')).length,
    circles: paths.filter(p => [...p.classList].some(c => c.indexOf('trail-group-') === 0)
                               && /a[\\d.]/i.test(p.getAttribute('d') || '')).length,
    loose: paths.filter(p => ![...p.classList].some(c => c.indexOf('trail-group-') === 0)).length,
    deaf: paths.filter(p => getComputedStyle(p).pointerEvents === 'none').length,
    markers: document.querySelectorAll('.leaflet-marker-pane > *').length,
    boxes: legend.filter(i => i.type === 'checkbox').length,
    off: legend.filter(i => i.type === 'checkbox' && !i.checked).length,
    radios: bases.filter(i => i.type === 'radio').length,
    tiles: Object.values(__MAP__._layers).filter(l => l._url).length,
    // The rail takes the top-left corner and the zoom steps aside for it. Left
    // rather than top, because both stand at 10 from the top and only the one
    // that moved says whether the corner made room.
    controls: [at(rail), at(zoom)],
    layerControls: document.querySelectorAll('.leaflet-control-layers').length}; }""")

# The scale, read so that neither axis takes part in proving the other: the
# horizontal comes off the distance marks the axis draws, that names which
# sample the crosshair dot sits on, and the vertical falls out of its height.
SCALE = """() => {
  const svg = document.querySelector('.trails-profile-panel svg');
  const rect = svg.getBoundingClientRect();
  const width = parseFloat(svg.getAttribute('viewBox').split(' ')[2]);
  const view = window.trailsProfilePanel.view();
  const shape = window.trailsProfile.shape;

  const alongs = [];
  for (const node of svg.querySelectorAll('text')) {
    const said = (node.textContent || '').trim();
    if (node.getAttribute('text-anchor') === 'middle' && /^\\d+(\\.\\d+)?$/.test(said)) {
      alongs.push({m: parseFloat(said) * 1000, x: parseFloat(node.getAttribute('x'))});
    }
  }
  alongs.sort((a, b) => a.m - b.m);
  if (alongs.length < 2) { return {why: 'fewer than two distance marks'}; }
  const first = alongs[0], last = alongs[alongs.length - 1];
  const along = (last.m - first.m) / (last.x - first.x);

  const dotAt = fraction => {
    const px = 52 + fraction * (view.shown / view.metresPerPixel);
    svg.dispatchEvent(new MouseEvent('mousemove', {bubbles: true,
      clientX: rect.left + (px / width) * rect.width, clientY: rect.top + rect.height / 2}));
    const dot = svg.querySelector('circle[r="2.5"]');
    if (!dot || dot.style.display === 'none') { return null; }
    const cx = parseFloat(dot.getAttribute('cx')), cy = parseFloat(dot.getAttribute('cy'));
    const where = first.m + (cx - first.x) * along;
    let best = -1, gap = Infinity, second = Infinity;
    for (let i = 0; i < shape.height.length; i += 1) {
      if (isNaN(shape.height[i])) { continue; }
      const away = Math.abs(shape.distance[i] - where);
      if (away < gap) { gap = away; best = i; }
    }
    for (let i = Math.max(0, best - 4); i <= Math.min(shape.height.length - 1, best + 4); i += 1) {
      if (i === best || isNaN(shape.height[i])) { continue; }
      second = Math.min(second, Math.abs(shape.distance[i] - where));
    }
    // Only usable where the axis names one sample and not two.
    return gap < second / 3 ? {sample: best, cx: cx, cy: cy} : null;
  };

  let a = null, b = null;
  for (const f of [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]) { a = a || dotAt(f); }
  for (const f of [0.95, 0.9, 0.85, 0.8, 0.75, 0.7]) { b = b || dotAt(f); }
  if (!a || !b || a.sample === b.sample) { return {why: 'no two points the axis names cleanly'}; }
  const alongM = shape.distance[b.sample] - shape.distance[a.sample];
  const upM = shape.height[b.sample] - shape.height[a.sample];
  return {zoom: view.zoom,
          along: alongM / (b.cx - a.cx),
          up: upM / (a.cy - b.cy),
          panel: view.metresPerPixel}; }"""

WHEEL_ON_CHART = """(spec) => {
  const chart = document.querySelector('.trails-profile-panel svg');
  const rect = chart.getBoundingClientRect();
  for (let i = 0; i < spec.times; i += 1) {
    chart.dispatchEvent(new WheelEvent('wheel', {bubbles: true, cancelable: true,
      deltaY: spec.delta, deltaMode: 0,
      clientX: rect.left + rect.width * 0.5, clientY: rect.top + rect.height / 2})); } }"""

PANES = """() => {
  const named = {};
  for (const pane of document.querySelectorAll('.leaflet-pane')) {
    const cls = [...pane.classList].find(c => c !== 'leaflet-pane');
    if (cls) { named[cls] = parseInt(getComputedStyle(pane).zIndex, 10); }
  }
  return named; }"""

# Where the crosshair's mark stands, and how far it is from the line it claims
# to be on. Projected onto every segment: the nearest point wins, which is why
# this reports the distance to the line and not the distance along it — on an
# out-and-back the nearest pass is not always the right one.
MARK = with_map("""() => {
  const svg = document.querySelector('.trails-profile-panel svg');
  const rect = svg.getBoundingClientRect();
  const view = window.trailsProfilePanel.view();
  const shape = window.trailsProfile.shape;
  const width = parseFloat(svg.getAttribute('viewBox').split(' ')[2]);
  const px = 52 + 0.5 * (view.shown / view.metresPerPixel);
  svg.dispatchEvent(new MouseEvent('mousemove', {bubbles: true,
    clientX: rect.left + (px / width) * rect.width, clientY: rect.top + rect.height / 2}));
  const mark = document.querySelector('.leaflet-trailsProfileHere-pane svg');
  if (!mark || mark.style.display === 'none') { return {shown: false}; }
  const at = __MAP__.layerPointToLatLng(L.DomUtil.getPosition(mark));
  const scale = Math.cos(at.lat * Math.PI / 180) * 111320, R = 111320;
  const x0 = at.lng * scale, y0 = at.lat * R;
  let best = Infinity;
  for (let i = 1; i < shape.along.length; i += 1) {
    const ax = shape.lon[i - 1] * scale, ay = shape.lat[i - 1] * R;
    const bx = shape.lon[i] * scale, by = shape.lat[i] * R;
    const dx = bx - ax, dy = by - ay, len = dx * dx + dy * dy;
    const t = len > 0 ? Math.max(0, Math.min(1, ((x0 - ax) * dx + (y0 - ay) * dy) / len)) : 0;
    best = Math.min(best, Math.hypot(x0 - (ax + t * dx), y0 - (ay + t * dy)));
  }
  // In pixels, because that is what the mark is placed in — Leaflet rounds a
  // pane's position for translate3d, so at zoom 9 half a pixel is 65 m and a
  // tolerance in metres would be measuring the zoom instead of the mark.
  const step = __MAP__.distance(__MAP__.containerPointToLatLng([0, 0]),
                                __MAP__.containerPointToLatLng([100, 0])) / 100;
  return {shown: true, away: best, px: best / step}; }""")

SEA = """() => {
  const svg = document.querySelector('.trails-profile-panel svg');
  const height = parseFloat(svg.getAttribute('height'));
  const view = window.trailsProfilePanel.view();
  const carries = (height - 34) * view.metresPerPixel;
  const floor = view.centre - carries / 2;
  const line = [...svg.querySelectorAll('line')].filter(l => l.getAttribute('stroke') === '#4fa3c7');
  return {'floor stands at m': floor,
          'sea level drawn': line.length,
          'clear of the floor px': line.length ? (height - 22) - parseFloat(line[0].getAttribute('y1')) : null}; }"""

#: Opening the tool first is not decoration. The control is in the dock, hidden
#: until something asks for it, and a check that drove it while it was hidden
#: would be driving a box with no size -- which is how this page's controls
#: cap themselves against each other.
PLAN_TOGGLE = """() => {
  if (window.trailsChrome) { window.trailsChrome.open('plan'); }
  document.querySelector('.trails-plan-control button').click(); }"""

OPEN_LIST = """() => { const box = document.querySelector('.trails-plan-control');
  const handle = [...box.querySelectorAll('div')]
    .find(d => /point/.test(d.textContent) && d.style.cursor === 'pointer');
  if (handle) { handle.click(); } return !!handle; }"""

#: Points, not children: a cut tour puts a heading between the rows, and a
#: check counting everything in the box would report a row per point plus one
#: per stage and call the difference a defect.
LIST_ROWS = """() => {
  const list = document.querySelector('.trails-plan-points');
  return list ? [...list.children].filter(row => !row.classList.contains('trails-plan-stage')).length : -1; }"""

DRAG_ROW = """(spec) => {
  const list = document.querySelector('.trails-plan-points');
  const rows = [...list.children].filter(row => !row.classList.contains('trails-plan-stage'));
  const from = rows[spec.from], to = rows[spec.to];
  if (!from || !to) { return false; }
  const data = new DataTransfer();
  const fire = (node, kind) => node.dispatchEvent(new DragEvent(kind,
    {bubbles: true, cancelable: true, dataTransfer: data}));
  fire(from, 'dragstart'); fire(to, 'dragover'); fire(to, 'drop'); fire(from, 'dragend');
  return true; }"""

#: A row holds two buttons since stages: the cut that ends one and the removal.
#: Addressed by what it is rather than by which comes first -- taking
#: ``querySelector('button')`` read the cut and reported that a removal had not
#: removed anything, which is the aiming-by-position trap one level up.
REMOVE_ROW = """(at) => {
  const list = document.querySelector('.trails-plan-points');
  const rows = [...list.children].filter(row => !row.classList.contains('trails-plan-stage'));
  const row = rows[at];
  if (!row) { return false; }
  const out = row.querySelector('.trails-plan-out');
  if (!out) { return false; }
  out.click(); return true; }"""

BOXES = """() => {
  // **The dock and not the control inside it.** Since the chrome, the plan
  // control is the dock's content: the dock is capped against the profile panel
  // and clips what does not fit, so the control's own rectangle reports the
  // height it would like to have and not the one a reader sees. Measuring the
  // content here read a 49 px overlap of something clipped out of sight, which
  // is the wrong question asked precisely.
  const plan = document.querySelector('.trails-dock');
  const profile = document.querySelector('.trails-profile-panel');
  const seen = node => { const r = node.getBoundingClientRect();
    return {top: r.top, bottom: r.bottom, height: r.height}; };
  const a = seen(plan), b = seen(profile);
  const clipped = getComputedStyle(plan).overflow;
  const list = document.querySelector('.trails-plan-points');
  let reachable = false;
  if (list && list.lastElementChild) {
    // Scrolled to the end, the last row has to be inside the box. That is the
    // question — not whether there is anything to scroll, which with three rows
    // in a 220 px cap there rightly is not.
    list.scrollTop = list.scrollHeight;
    const last = list.lastElementChild.getBoundingClientRect();
    const held = list.getBoundingClientRect();
    reachable = last.bottom <= held.bottom + 1 && last.top >= held.top - 1;
    list.scrollTop = 0;
  }
  return {overlap: Math.max(0, a.bottom - b.top),
          'dock clips': clipped === 'hidden',
          'profile height': Math.round(b.height),
          'list cap': list ? parseFloat(list.style.maxHeight) : null,
          'rows': list ? list.children.length : 0,
          'last row reachable': reachable}; }"""

STRETCH_PROFILE = """(px) => {
  const panel = document.querySelector('.trails-profile-panel'), grip = panel.firstChild;
  const rect = grip.getBoundingClientRect(), start = rect.top + rect.height / 2;
  grip.dispatchEvent(new MouseEvent('mousedown',
    {bubbles: true, cancelable: true, clientY: start, clientX: rect.left + 20}));
  document.dispatchEvent(new MouseEvent('mousemove',
    {bubbles: true, clientY: start - px, clientX: rect.left + 20}));
  document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); }"""


# ---------------------------------------------------------------------------
# The checks.
# ---------------------------------------------------------------------------


def select(page: Any, chain: str) -> bool:
    """Select a chain and wait for its series to be composed.

    **Waiting rather than sleeping.** The panel decodes the chain out of the
    carried graph a microtask or more after the click, so a fixed pause is a
    guess that is too long on a fast machine and too short on a slow one.

    Args:
        page: The driven page
        chain: The ``trail-group-`` class of the chain to select

    Returns:
        Whether the chain was found and its series arrived
    """
    # **Idempotent, because firing a chain's click is a toggle.** Selecting one
    # that is already selected clears it, and every reading after that skips or
    # reads an empty panel — quietly, which is the worst way for a suite to go
    # wrong. It has bitten two checks; it belongs here and not in each of them.
    already = page.evaluate(
        "(cls) => !!(window.trailsProfile && window.trailsProfile.className === cls)",
        chain,
    )
    if not already and not page.evaluate(SELECT_CHAIN, chain):
        return False
    try:
        page.wait_for_function("() => window.trailsProfile && window.trailsProfile.shape", timeout=15_000)
    except Exception:
        return False
    return True


def furniture(page: Any) -> Check:
    """What the page draws before anything is clicked.

    Args:
        page: The driven page

    Returns:
        The counts, against what the last build measured
    """
    seen = page.evaluate(FURNITURE)
    rail, zoom = (seen["controls"] + [None, None])[:2]
    return Check(
        "the page's furniture",
        [
            Reading("paths in the overlay pane", seen["paths"], 11589, holds=False),
            Reading("of them chains drawn as lines", seen["lines"], 11290, holds=False),
            Reading("and chains drawn as circle markers", seen["circles"], 298, holds=False),
            # **The decomposition has to add up.** The count above moves when the
            # sources move; this does not, and it is what catches something drawn
            # into a pane it has no business being in — a planned route carries no
            # chain class, so it would land here.
            Reading("paths carrying no chain class", seen["loose"], 1),
            Reading(
                "and the three add up to the whole",
                seen["lines"] + seen["circles"] + seen["loose"],
                seen["paths"],
            ),
            # The one non-interactive path is the park boundary, which opts out
            # of pointer events so clicks reach the trails under its fill. A
            # second one means something else stopped answering clicks.
            Reading("paths deaf to the pointer", seen["deaf"], 1),
            Reading("things in the marker pane", seen["markers"], 198, holds=False),
            Reading("checkboxes in the legend", seen["boxes"], 30, holds=False),
            Reading("of them switched off", seen["off"], 7, holds=False),
            Reading("base maps offered", seen["radios"], 2),
            # Folium hands every base layer to the map; the legend takes the
            # unwanted ones off again, and nothing else will.
            Reading("tile layers actually on the map", seen["tiles"], 1),
            Reading("separate layer controls", seen["layerControls"], 0),
            # The rail takes the corner and the zoom steps aside for it. A
            # zoom still at 10 would mean the corner never made room and the two
            # are stacked on each other, which is what this replaced.
            Reading("the tool rail, px from the left", rail, 10, within=1),
            Reading("zoom buttons, px from the left", zoom, 66, within=1),
        ],
    )


def map_wheel(page: Any) -> Check:
    """The wheel over open map, which is an acceptance figure from phase 3.

    Args:
        page: The driven page

    Returns:
        The zoom before and after two notches
    """
    zoom = page.evaluate(f"() => {MAP_OBJECT}.getZoom()")
    box = page.locator(".leaflet-container").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -240)
    page.wait_for_timeout(900)
    after = page.evaluate(f"() => {MAP_OBJECT}.getZoom()")
    page.evaluate(f"(z) => {MAP_OBJECT}.setZoom(z)", zoom)
    page.wait_for_timeout(600)
    return Check(
        "a wheel over open map",
        [
            Reading("zoom before", zoom, 9, holds=False),
            Reading("zoom after", after, 11, holds=False),
        ],
    )


def true_scale(page: Any) -> Check:
    """One metres-per-pixel for both axes, at rest and zoomed in.

    The panel's central claim, and the one thing about it a source test cannot
    reach: that the angle drawn is the angle on the ground.

    Args:
        page: The driven page, with a long chain selected

    Returns:
        The two scales at three zooms, and how far apart they are
    """
    page.evaluate(
        """() => { const chart = document.querySelector('.trails-profile-panel svg');
        chart.dispatchEvent(new MouseEvent('dblclick', {bubbles: true, cancelable: true})); }"""
    )
    page.wait_for_timeout(400)
    readings = []
    for label, notches in (("at rest", 0), ("zoomed in", 8), ("at the ceiling", 40)):
        if notches:
            page.evaluate(WHEEL_ON_CHART, {"times": notches, "delta": -100})
            page.wait_for_timeout(400)
        seen = page.evaluate(SCALE)
        if "why" in seen:
            readings.append(Reading(f"{label}: both axes agree", seen["why"], "a reading"))
            continue
        readings.append(
            Reading(
                f"{label} (zoom {seen['zoom']:.2f}), the two axes apart",
                abs(seen["up"] / seen["along"] - 1),
                0.0,
                within=1e-6,
                note=f"{seen['along']:.6f} along, {seen['up']:.6f} up",
            )
        )
    return Check("the profile is drawn true to scale", readings)


def zoom_ceiling(page: Any) -> Check:
    """The zoom stops at one height reading per pixel and no further.

    Args:
        page: The driven page, zoomed to the ceiling

    Returns:
        The scale reached against the series' own mean spacing
    """
    seen = page.evaluate(
        """() => { const view = window.trailsProfilePanel.view();
        const shape = window.trailsProfile.shape;
        let read = 0;
        for (const h of shape.height) { if (!isNaN(h)) { read += 1; } }
        return {mpp: view.metresPerPixel, zoom: view.zoom,
                spacing: shape.total / (read - 1)}; }"""
    )
    return Check(
        "the zoom stops where the readings do",
        [
            Reading(
                "metres a pixel at the ceiling, against the reading spacing",
                seen["mpp"] / seen["spacing"],
                1.0,
                within=0.05,
                note=f"{seen['mpp']:.3f} m/px against {seen['spacing']:.3f} m between readings",
            ),
        ],
    )


def curve_wheel(page: Any, zoomable: bool) -> Check:
    """The wheel over the curve, which the chart takes only when it can use it.

    A panel that swallows a wheel and does nothing with it reads as the map
    having frozen, so the chart takes it exactly where there is detail under the
    drawing to reach and passes it on everywhere else.

    Args:
        page: The driven page, with a chain selected
        zoomable: Whether this chain is drawn coarser than its own samples

    Returns:
        Whether the map's zoom moved, and whether it should have
    """
    before = page.evaluate(f"() => {MAP_OBJECT}.getZoom()")
    page.evaluate(WHEEL_ON_CHART, {"times": 2, "delta": -200})
    page.wait_for_timeout(900)
    after = page.evaluate(f"() => {MAP_OBJECT}.getZoom()")
    where = "a chain with detail to reach" if zoomable else "a chain already drawn finer than its samples"
    return Check(
        f"a wheel over the curve, on {where}",
        [Reading("the map's zoom moved", after != before, not zoomable)],
    )


def crosshair_mark(page: Any) -> Check:
    """The mark the crosshair puts on the map: on its line, and above the route.

    Args:
        page: The driven page, with a chain selected

    Returns:
        How far the mark lies off the line, and the panes in the order they paint
    """
    seen = page.evaluate(MARK)
    panes = page.evaluate(PANES)
    here = panes.get("leaflet-trailsProfileHere-pane")
    route = panes.get("leaflet-trailsPlanRoute-pane")
    return Check(
        "the crosshair marks its position on the map",
        [
            Reading("a mark is drawn", seen.get("shown", False), True),
            # Placed by interpolating between two vertices, so it is on the line
            # by construction; what this catches is the wrong axis being walked.
            Reading(
                "pixels off the drawn line",
                seen.get("px", 999),
                0.0,
                within=1.0,
                note=f"{seen.get('away', 0):.1f} m at this zoom",
            ),
            Reading("its pane sits above the planned route", (here or 0) > (route or 0), True, note=f"{here} against {route}"),
            Reading("and below the markers", (here or 0) < panes.get("leaflet-marker-pane", 0), True),
        ],
    )


def sea_level(page: Any) -> Check:
    """Sea level is the floor of the box, and stands clear of it.

    Args:
        page: The driven page, with a chain selected at rest

    Returns:
        Where the floor stands and whether the 0 m line is drawn clear of it
    """
    seen = page.evaluate(SEA)
    return Check(
        "the floor of the box means sea level",
        [
            Reading("the floor stands below nought", seen["floor stands at m"] < 0, True, note=f"{seen['floor stands at m']:.0f} m"),
            Reading("the 0 m line is drawn", seen["sea level drawn"], 1),
            Reading("px it stands clear of the floor", seen["clear of the floor px"] or 0, 18, within=1),
        ],
    )


def popup_click(page: Any) -> Check:
    """A click inside a chain's detail is not a click on the ground.

    **The subject moved and the defect did not.** A popup used to float over the
    map in a pane of its own, and plan mode -- which owns every click on the
    container -- stepped around the control container and walked over it, so the
    close button placed a waypoint behind the popup and left it open. Popups do
    not float any more: the chrome takes each one into a panel of its own, which
    is a different element in a different place and is exactly as easy to walk
    over. The check follows the content rather than the widget it used to live
    in, which is the same rule as addressing a row's buttons by name.

    Args:
        page: The driven page, in plan mode

    Returns:
        Whether reading the panel placed a waypoint, and whether it closed
    """
    page.evaluate(
        with_map("""(cls) => { const map = __MAP__;
        let found = null;
        const walk = l => { if (found) return;
          if (l.options && l.options.className === cls) { found = l; return; }
          if (l.eachLayer) l.eachLayer(walk); };
        map.eachLayer(walk);
        if (found) { const at = found.getLatLngs()[Math.floor(found.getLatLngs().length / 2)];
          map.setView(at, 12); found.openPopup(at); } }"""),
        LONG_CHAIN,
    )
    page.wait_for_timeout(1200)
    where = page.evaluate(
        """() => { const panel = document.querySelector('.trails-detail');
        if (!panel || panel.style.display === 'none') { return null; }
        const close = panel.querySelector('.trails-chrome-close');
        const body = panel.querySelector('.trails-chrome-body');
        const shut = close.getBoundingClientRect(), text = body.getBoundingClientRect();
        return {close: {x: shut.left + shut.width / 2, y: shut.top + shut.height / 2},
                text: {x: text.left + text.width / 2, y: text.top + 24},
                rows: panel.querySelectorAll('tr').length}; }"""
    )
    if not where:
        return Check("a click in a chain's detail", skipped="the detail panel did not open")

    before = page.evaluate("() => window.trailsPlan.state().points.length")
    page.mouse.click(where["text"]["x"], where["text"]["y"])
    page.wait_for_timeout(1000)
    after_text = page.evaluate("() => window.trailsPlan.state().points.length")
    page.mouse.click(where["close"]["x"], where["close"]["y"])
    page.wait_for_timeout(1000)

    return Check(
        "a click in a chain's detail is not a click on the ground",
        [
            # The popup carried 13 rows when it floated and carries them still:
            # the chrome moves the node folium built, it does not rebuild it.
            Reading("rows the detail holds", where["rows"] > 0, True, note=f"{where['rows']} rows"),
            Reading("waypoints placed by reading it", after_text - before, 0),
            Reading("waypoints placed by the close button", page.evaluate("() => window.trailsPlan.state().points.length") - before, 0),
            Reading(
                "and it closed",
                page.evaluate("() => window.trailsChrome.state().detail"),
                False,
            ),
        ],
    )


def stations_and_list(page: Any, places: list[dict[str, float]]) -> Check:
    """The points a route was planned with: their distances, and the list.

    Args:
        page: The driven page, in plan mode
        places: Positions to put waypoints at

    Returns:
        What the stations say, and what dragging and removing a row did
    """
    for place in places:
        page.evaluate("(at) => window.trailsPlan.place(at.lat, at.lon)", place)
        page.wait_for_timeout(2000)
    page.wait_for_timeout(2500)
    state = page.evaluate("() => window.trailsPlan.state()")
    stations = state.get("stations") or []
    forwards = all(b >= a - 1e-6 for a, b in zip(stations, stations[1:], strict=False))
    readings = [
        Reading("a station for every point", len(stations), len(state["points"])),
        # A crossing adds no walking distance and an unsettled leg adds none
        # either, so these may repeat — but they may never go backwards.
        Reading("they never run backwards", forwards, True),
        Reading("the last one is the whole walk", abs((stations[-1] if stations else 0) - state["walked"]), 0.0, within=0.5),
    ]

    opened = page.evaluate(OPEN_LIST)
    page.wait_for_timeout(600)
    readings.append(Reading("the count opens the list", opened, True))
    readings.append(Reading("a row for every point", page.evaluate(LIST_ROWS), len(state["points"])))

    before = page.evaluate("() => window.trailsPlan.state().points.map(p => Math.round(p.lat * 1e6))")
    if len(before) >= 4 and page.evaluate(DRAG_ROW, {"from": 3, "to": 1}):
        page.wait_for_timeout(3000)
        after = page.evaluate("() => window.trailsPlan.state().points.map(p => Math.round(p.lat * 1e6))")
        # A splice and not a swap: the dragged point is taken out and put back
        # in, and everything it passed shifts one place the other way.
        readings.append(Reading("dragging row 4 onto row 2 splices", after, [before[0], before[3], before[1], before[2]]))

    was = page.evaluate("() => window.trailsPlan.state().points.length")
    if page.evaluate(REMOVE_ROW, 1):
        page.wait_for_timeout(3000)
        readings.append(Reading("the row's own button takes it out", page.evaluate("() => window.trailsPlan.state().points.length"), was - 1))
    return Check("a route's own points, on the profile and in the list", readings)


def sharing_the_room(page: Any) -> Check:
    """Two controls over one map, and neither covering the other.

    Args:
        page: The driven page, in plan mode with a list open

    Returns:
        The overlap at three profile heights and two window sizes
    """
    readings = []
    for label, stretch in (("at rest", 0), ("profile 200 px taller", 200), ("and 400 more", 400)):
        if stretch:
            page.evaluate(STRETCH_PROFILE, stretch)
            page.wait_for_timeout(900)
        seen = page.evaluate(BOXES)
        readings.append(
            Reading(
                f"{label}: px of the tool dock under the profile",
                round(seen["overlap"]),
                0,
                note=f"profile {seen['profile height']} px, list cap {seen['list cap']}",
            )
        )
        readings.append(Reading(f"{label}: the last row can still be reached", seen["last row reachable"], True, note=f"{seen['rows']} rows"))
        # What makes measuring the dock rather than its content the right
        # question: without the clip, content taller than the cap would show
        # through and the overlap above would be a fiction.
        readings.append(Reading(f"{label}: and the dock clips what does not fit", seen["dock clips"], True))

    page.set_viewport_size({"width": 1400, "height": 620})
    page.wait_for_timeout(1200)
    seen = page.evaluate(BOXES)
    readings.append(Reading("in a 620 px window: overlap", round(seen["overlap"]), 0))
    # Clamped only where it was asked for, a panel taller than the map puts its
    # own grip off the top and out of reach for good.
    readings.append(Reading("the profile stayed inside the map", seen["profile height"] <= 620, True, note=f"{seen['profile height']} px"))
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(1000)
    return Check("two controls sharing one map", readings)


def chrome_layout(page: Any) -> Check:
    """One layout decided by one number, and what it puts where.

    Driven at three widths in one session: a desktop, a phone held upright and
    the same phone turned sideways. The reading that matters at each is how much
    of the map nothing is standing on, worked out **on a grid rather than by
    subtracting rectangles** -- the panels overlap each other, so subtracting
    their areas would subtract the same pixels twice.

    Args:
        page: The driven page, with nothing selected

    Returns:
        What stands where at each width
    """
    free = """() => {
      const box = node => { if (!node || node.offsetParent === null) { return null; }
        const r = node.getBoundingClientRect();
        return {x: r.x, y: r.y, w: r.width, h: r.height}; };
      const map = document.querySelector('.leaflet-container').getBoundingClientRect();
      const over = ['.trails-rail', '.trails-burger', '.trails-dock', '.trails-menu',
                    '.trails-detail', '.trails-profile-panel', '.leaflet-control-zoom',
                    '.leaflet-bottom.leaflet-left .leaflet-control']
        .map(sel => box(document.querySelector(sel))).filter(Boolean);
      let clear = 0, cells = 0;
      for (let y = map.y; y < map.y + map.height; y += 4) {
        for (let x = map.x; x < map.x + map.width; x += 4) {
          cells += 1;
          if (!over.some(b => x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h)) { clear += 1; }
        } }
      const zoom = document.querySelector('.leaflet-control-zoom');
      return {free: Math.round(1000 * clear / cells) / 10,
              rail: !!box(document.querySelector('.trails-rail')),
              burger: !!box(document.querySelector('.trails-burger')),
              zoomLeft: zoom ? Math.round(zoom.getBoundingClientRect().left) : null,
              state: window.trailsChrome.state()}; }"""

    readings = []
    for label, width, height in (("desktop", 1400, 900), ("upright", 390, 844), ("sideways", 844, 390)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(900)
        page.evaluate("() => window.trailsChrome.close()")
        page.wait_for_timeout(400)
        seen = page.evaluate(free)
        narrow = width < seen["state"]["threshold"]
        readings.append(Reading(f"{label}: map free with nothing asked for", seen["free"], 96, within=4, holds=False))
        readings.append(Reading(f"{label}: the rail stands", seen["rail"], not narrow))
        readings.append(Reading(f"{label}: the burger stands", seen["burger"], narrow))

    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(900)
    # Opening a tool docks it beside the rail, and the same call closes it: a
    # rail button is a switch and not a one-way door.
    page.evaluate("() => window.trailsChrome.open('layers')")
    page.wait_for_timeout(500)
    opened = page.evaluate("() => window.trailsChrome.state().tool")
    boxes = page.evaluate("() => document.querySelectorAll('.trails-dock .trails-legend input[type=checkbox]').length")
    page.evaluate("() => window.trailsChrome.open('layers')")
    page.wait_for_timeout(400)
    readings.append(Reading("a rail button docks its panel", opened, "layers"))
    readings.append(Reading("and the legend is what is in it", boxes, 30, holds=False))
    readings.append(Reading("and the same button puts it away", page.evaluate("() => window.trailsChrome.state().tool"), None))
    return Check("one layout, decided by the width of the map", readings)


def pinch_the_curve(page: Any) -> Check:
    """Two fingers apart is in, together is out.

    **A dispatched touch proves the arithmetic and not the plumbing**, which is
    the caveat this suite already records for HTML5 dragging: that a handler
    answers a synthetic event says nothing about whether the browser ever
    delivers a real one. What it does prove is the part that could be wrong in a
    way nobody would notice -- that the ground between the two fingers stays
    between them, so a pinch reads as a lens and not as a slider.

    Args:
        page: The driven page, with a zoomable chain selected

    Returns:
        Where the window went, spreading and then closing the fingers
    """
    gesture = """(spread) => {
      const chart = document.querySelector('.trails-profile-panel svg');
      const box = chart.getBoundingClientRect();
      const midX = box.left + box.width / 2, midY = box.top + box.height / 2;
      const fire = (kind, half) => {
        // A plain Event carrying a touch list: Firefox has no Touch constructor
        // to build a real TouchEvent with, and the handler reads clientX and
        // length off whatever it is given.
        const event = new Event(kind, {bubbles: true, cancelable: true});
        event.touches = half === null ? [] : [
          {clientX: midX - half, clientY: midY}, {clientX: midX + half, clientY: midY}];
        chart.dispatchEvent(event);
      };
      fire('touchstart', 40);
      fire('touchmove', 40 * spread);
      fire('touchend', null);
      return true; }"""

    # From the whole chain, put there rather than assumed: the check before this
    # one leaves the window at the ceiling, and a gesture measured from an
    # unknown starting point measures nothing.
    reset = """() => { const chart = document.querySelector('.trails-profile-panel svg');
        chart.dispatchEvent(new MouseEvent('dblclick', {bubbles: true, cancelable: true})); }"""
    page.evaluate(reset)
    page.wait_for_timeout(500)

    start = page.evaluate("() => window.trailsProfilePanel.view()")
    page.evaluate(gesture, 3.0)
    page.wait_for_timeout(600)
    apart = page.evaluate("() => window.trailsProfilePanel.view()")
    page.evaluate(gesture, 0.25)
    page.wait_for_timeout(600)
    together = page.evaluate("() => window.trailsProfilePanel.view()")

    # And back to the whole chain, or every check after this one reads a window
    # this one opened.
    page.evaluate(reset)
    page.wait_for_timeout(400)

    return Check(
        "two fingers on the curve",
        [
            Reading("it starts at the whole chain", round(start["zoom"], 3), 1.0),
            Reading("apart zooms in", apart["zoom"] > 1.5, True, note=f"zoom {apart['zoom']:.2f}"),
            # The ceiling is the data's: one reading per pixel, and not a taste.
            Reading("and never past the readings", apart["zoom"] <= apart["closest"] + 1e-6, True, note=f"ceiling {apart['closest']:.2f}"),
            Reading("together zooms out", together["zoom"] < apart["zoom"], True, note=f"zoom {together['zoom']:.2f}"),
            Reading("and never below the whole chain", together["zoom"] >= 1.0 - 1e-9, True),
        ],
    )


def narrow_sheets(page: Any) -> Check:
    """On a narrow screen only one panel may be drawn, and a tool covers rather than closes.

    The dock, the menu and the detail are the same full-screen sheet below the
    threshold, so two of them showing at once is two readable panels stacked on
    each other with the later-written one winning -- which is the defect the
    legend and the layer control had already produced once on this map, and the
    reason what is open is kept as three facts rather than as three styles.

    Args:
        page: The driven page, with a chain selected

    Returns:
        What is drawn as a tool is opened over an open detail and closed again
    """
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(900)
    page.evaluate(SELECT_CHAIN, LONG_CHAIN)
    page.wait_for_timeout(900)

    shown = """() => {
      const drawn = sel => { const node = document.querySelector(sel);
        return !!node && node.offsetParent !== null; };
      return {dock: drawn('.trails-dock'), menu: drawn('.trails-menu'),
              detail: drawn('.trails-detail'), state: window.trailsChrome.state()}; }"""

    page.evaluate("() => window.trailsChrome.close()")
    page.evaluate(
        """(cls) => { const map = window[Object.keys(window).find(k => k.startsWith('map_'))];
        let found = null;
        const walk = l => { if (found) return;
          if (l.options && l.options.className === cls) { found = l; return; }
          if (l.eachLayer) l.eachLayer(walk); };
        map.eachLayer(walk);
        if (found) { found.fire('click'); } }""",
        LONG_CHAIN,
    )
    page.wait_for_timeout(900)
    reading = page.evaluate(shown)

    page.evaluate("() => window.trailsChrome.open('layers')")
    page.wait_for_timeout(700)
    over = page.evaluate(shown)

    page.evaluate("() => window.trailsChrome.open('layers')")
    page.wait_for_timeout(700)
    back = page.evaluate(shown)

    page.evaluate("() => window.trailsChrome.close()")
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(900)

    return Check(
        "one sheet at a time on a narrow screen",
        [
            Reading("a tap draws the detail", reading["detail"], True),
            Reading("and only that", reading["dock"] or reading["menu"], False),
            Reading("a tool covers it", over["dock"] and not over["detail"], True),
            # Covered, not closed: the chrome still says a detail is open, and
            # that is the difference between stepping aside and being discarded.
            Reading("but the detail is still open", over["state"]["detail"], True),
            Reading("and closing the tool gives it back", back["detail"] and not back["dock"], True),
        ],
    )


def room_on_a_short_screen(page: Any) -> Check:
    """A panel at the foot gives room back where there is none to take.

    Measured before this was built: on a phone held sideways the row holding the
    download button, the point count, the licences and the colour key came out
    **66 px** against a **78 px** drawing -- the licence list wraps to three
    lines on a screen that narrow and to one on a desktop, so the small screen
    paid double for the same sentence. It folds behind an *i* there, and the *i*
    does not exist where the row already fits.

    Args:
        page: The driven page, with a chain selected

    Returns:
        What the row and the drawing measure, folded and unfolded, at both sizes
    """
    parts = """() => {
      const panel = document.querySelector('.trails-profile-panel');
      const body = panel.children[2];
      const high = node => node ? Math.round(node.getBoundingClientRect().height) : null;
      const more = document.querySelector('.trails-profile-more');
      return {panel: high(panel), meta: high(body.children[0]), chart: high(body.children[1]),
              more: !!(more && more.offsetParent !== null)}; }"""

    page.set_viewport_size({"width": 844, "height": 390})
    page.wait_for_timeout(1200)
    folded = page.evaluate(parts)
    page.evaluate("() => document.querySelector('.trails-profile-more').click()")
    page.wait_for_timeout(500)
    opened = page.evaluate(parts)
    page.evaluate("() => document.querySelector('.trails-profile-more').click()")
    page.wait_for_timeout(400)

    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(1200)
    desk = page.evaluate(parts)

    return Check(
        "a short screen gets its drawing back",
        [
            Reading("sideways: the licences are folded", folded["more"], True),
            Reading("sideways: px the row takes", folded["meta"], 33, within=12, holds=False),
            # And the freed pixels go to the drawing rather than to the map:
            # the share is on the chart while the furniture is what it costs, so
            # shrinking the furniture without moving the share gives the map the
            # room and the curve none of it.
            Reading("and the drawing gets them", folded["chart"], 109, within=6, note="78 px before"),
            Reading("with the panel still about half the screen", folded["panel"] <= 215, True, note=f"{folded['panel']} px of 390"),
            # Nothing is withheld: the sentence a reader has to see before
            # pressing Download is one tap away and says so.
            Reading("the i opens them again", opened["meta"] > folded["meta"], True, note=f"{opened['meta']} px"),
            # And on a desktop there is nothing to fold, so there is no i.
            Reading("desktop: no i at all", desk["more"], False),
            Reading("desktop: px the row takes", desk["meta"], 33, within=2),
            Reading("desktop: px the drawing takes", desk["chart"], 205, within=2),
        ],
    )


def a_finger_can_use_it(page: Any) -> Check:
    """The targets a finger needs, and the edits it can reach.

    **Keyed off the pointer and not off the width**: how big a target has to be
    is a question about hands, and a touch laptop at 1400 px needs what a mouse
    in a 390 px window does not. The check drives the class the media query sets
    rather than pretending to have a finger -- what is being measured is the
    geometry, and whether Firefox calls a synthetic touch context coarse is a
    different question and not this page's.

    Args:
        page: The driven page, in plan mode with points down and the list open

    Returns:
        What the row measures with each pointer, and whether the arrows move a point
    """
    # **It has to open the panel it is measuring.** A tap on a trail docks the
    # chain's detail and closes whatever tool was open -- by design, and the
    # check before this one taps a trail. Measuring here without opening it
    # again measures a box with no size, which is the detached-DOM trap one
    # level up.
    page.evaluate("() => window.trailsChrome.open('plan')")
    page.wait_for_timeout(600)
    # And it asks whether the list is open rather than pressing the handle: the
    # handle is a toggle, the check before this one has already opened it, and a
    # second press shuts it. Driving a toggle blind is how a check ends up
    # measuring the opposite of what it asked for.
    page.evaluate(
        """() => { const list = document.querySelector('.trails-plan-points');
        if (list && list.style.display !== 'none') { return; }
        const box = document.querySelector('.trails-plan-control');
        const handle = [...box.querySelectorAll('div')]
          .find(d => /point/.test(d.textContent) && d.style.cursor === 'pointer');
        if (handle) { handle.click(); } }"""
    )
    page.wait_for_timeout(600)

    sizes = """() => {
      const size = node => { if (!node || node.offsetParent === null) return null;
        const r = node.getBoundingClientRect();
        return [Math.round(r.width), Math.round(r.height)]; };
      const rows = [...document.querySelectorAll('.trails-plan-points > div')]
        .filter(row => !row.classList.contains('trails-plan-stage'));
      return {row: size(rows[0]),
              out: size(document.querySelector('.trails-plan-out')),
              up: size(document.querySelector('.trails-plan-up')),
              grip: size(document.querySelector('.trails-plan-grip')),
              rows: rows.length}; }"""

    fine = page.evaluate(sizes)
    page.evaluate("() => window.trailsChrome.coarse(true)")
    page.wait_for_timeout(500)
    coarse = page.evaluate(sizes)

    # And the arrows are not decoration: one press swaps a point with its
    # neighbour, which is `moveBy` -- the pin's own gesture, already here.
    before = page.evaluate("() => window.trailsPlan.state().points.map(p => Math.round(p.lat * 1e5))")
    moved = page.evaluate(
        """() => { const rows = [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage'));
        const up = rows[2] && rows[2].querySelector('.trails-plan-up');
        if (!up) { return false; }
        up.click(); return true; }"""
    )
    page.wait_for_timeout(2500)
    after = page.evaluate("() => window.trailsPlan.state().points.map(p => Math.round(p.lat * 1e5))")

    page.evaluate("() => window.trailsChrome.coarse(null)")
    page.wait_for_timeout(400)
    back = page.evaluate(sizes)

    swapped = before[:1] + [before[2], before[1]] + before[3:] if len(before) > 2 else before
    return Check(
        "what a finger needs",
        [
            Reading("with a mouse: the row's own height", fine["row"][1] if fine["row"] else 0, 21, within=3),
            Reading("with a mouse: no arrows drawn", fine["up"], None),
            Reading("with a mouse: the drag grip is there", fine["grip"] is not None, True),
            Reading("coarse: px the row takes", coarse["row"][1] if coarse["row"] else 0, 44, within=2),
            Reading("coarse: the × is at least 40 px", min(coarse["out"] or [0, 0]) >= 40, True, note=str(coarse["out"])),
            Reading("coarse: the arrows are at least 40 px", min(coarse["up"] or [0, 0]) >= 40, True, note=str(coarse["up"])),
            # A grip that promises a drag no browser here implements is a lie,
            # so it goes and the arrows take its place.
            Reading("coarse: the drag grip is gone", coarse["grip"], None),
            Reading("an arrow swaps the point with its neighbour", after, swapped, note=f"{moved}"),
            # And nothing of it survives going back to a mouse.
            Reading("back with a mouse: the row is 21 px again", back["row"][1] if back["row"] else 0, 21, within=3),
            Reading("back with a mouse: no arrows drawn", back["up"], None),
        ],
    )


def a_way_back_to_the_whole(page: Any) -> Check:
    """A reader can find the way out of a zoom, and a finger has one at all.

    Double-clicking the curve has put the whole chain back since the zoom was
    built and nothing said so. An undiscoverable gesture is a gesture most
    readers do not have -- and ``dblclick`` never reaches a finger at all.

    Args:
        page: The driven page, with a zoomable chain selected

    Returns:
        Whether the way back appears, works, and puts itself away again
    """
    zoom = """(spread) => {
      const chart = document.querySelector('.trails-profile-panel svg');
      const box = chart.getBoundingClientRect();
      const midX = box.left + box.width / 2, midY = box.top + box.height / 2;
      const fire = (kind, half) => {
        const event = new Event(kind, {bubbles: true, cancelable: true});
        event.touches = half === null ? [] : [
          {clientX: midX - half, clientY: midY}, {clientX: midX + half, clientY: midY}];
        event.changedTouches = [{clientX: midX, clientY: midY}];
        chart.dispatchEvent(event);
      };
      fire('touchstart', 40); fire('touchmove', 40 * spread); fire('touchend', null); }"""

    tap = """() => {
      const chart = document.querySelector('.trails-profile-panel svg');
      const box = chart.getBoundingClientRect();
      const at = {clientX: box.left + box.width / 2, clientY: box.top + box.height / 2};
      const fire = () => { const event = new Event('touchend', {bubbles: true, cancelable: true});
        event.touches = []; event.changedTouches = [at]; chart.dispatchEvent(event); };
      fire(); fire(); }"""

    shown = "() => { const node = document.querySelector('.trails-profile-whole'); return !!(node && node.offsetParent !== null); }"
    at = "() => window.trailsProfilePanel.view().zoom"

    resting = page.evaluate(shown)
    page.evaluate(zoom, 3.0)
    page.wait_for_timeout(600)
    zoomed = {"shown": page.evaluate(shown), "zoom": page.evaluate(at)}

    page.evaluate("() => document.querySelector('.trails-profile-whole').click()")
    page.wait_for_timeout(600)
    pressed = {"shown": page.evaluate(shown), "zoom": page.evaluate(at)}

    page.evaluate(zoom, 3.0)
    page.wait_for_timeout(600)
    page.evaluate(tap)
    page.wait_for_timeout(600)
    tapped = page.evaluate(at)

    return Check(
        "a way back to the whole chain",
        [
            Reading("at rest there is nothing to go back from", resting, False),
            Reading("zoomed in, it says so", zoomed["shown"], True, note=f"zoom {zoomed['zoom']:.2f}"),
            Reading("and pressing it puts the chain back", round(pressed["zoom"], 3), 1.0),
            Reading("after which it puts itself away", pressed["shown"], False),
            # The finger's own way, since dblclick never reaches one.
            Reading("two taps do the same", round(tapped, 3), 1.0),
        ],
    )


def the_plan_bar(page: Any) -> Check:
    """Planning on a phone, with the ground it is planned on left showing.

    Measured before this was built, with real taps at 390 x 844: the profile
    panel opened on the **first** point at 355 px and grew to 389 on the second,
    so the map a reader was tapping shrank to **439 px** -- and with the plan
    panel shut the only thing on the screen was the burger, so nothing said plan
    mode was on and every tap placed a point. Reaching the point list was four
    taps and undo was three.

    Args:
        page: The driven page, in plan mode with points down

    Returns:
        What the bar says and reaches, and what it left of the map

    """
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(900)
    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(600)

    seen = """() => {
      const box = sel => { const n = document.querySelector(sel);
        if (!n || n.offsetParent === null) { return null; }
        const r = n.getBoundingClientRect();
        return {w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top)}; };
      const bar = document.querySelector('.trails-planbar');
      return {bar: box('.trails-planbar'),
              says: bar ? bar.querySelector('b').textContent : null,
              profile: box('.trails-profile-panel'),
              dock: box('.trails-dock'),
              rows: (() => { const l = document.querySelector('.trails-plan-points');
                return l && l.style.display !== 'none' ? l.children.length : 0; })(),
              state: window.trailsChrome.state()}; }"""

    planning = page.evaluate(seen)
    before = page.evaluate("() => window.trailsPlan.state().points.length")

    # One tap on the figures, and the list is open. Four taps before this.
    page.evaluate("() => { document.querySelector('.trails-planbar-figures').click(); }")
    page.wait_for_timeout(900)
    reached = page.evaluate(seen)

    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(500)
    # **A point placed here on purpose.** Undo takes back the last *change*, and
    # the check before this one ends with a reorder — pressing undo then would
    # restore an order and leave the count where it was, which is right and
    # would read here as the button doing nothing.
    laid = "() => window.trailsPlan.state().points.map(p => Math.round(p.lat * 1e5))"
    was = page.evaluate(laid)
    steps_before = page.evaluate("() => window.trailsPlan.state().undoable")
    page.evaluate(
        """() => { const points = window.trailsPlan.state().points;
        const last = points[points.length - 1];
        window.trailsPlan.place(last.lat + 0.004, last.lon + 0.004); }"""
    )
    page.wait_for_timeout(2400)
    before = page.evaluate("() => window.trailsPlan.state().points.length")
    pressable = page.evaluate(
        """() => { const b = document.querySelectorAll('.trails-planbar button')[0];
        return {there: !!(b && b.offsetParent !== null), off: b ? b.disabled : null,
                steps: window.trailsPlan.state().undoable}; }"""
    )
    pressable["before the place"] = steps_before
    page.evaluate("() => { document.querySelectorAll('.trails-planbar button')[0].click(); }")
    page.wait_for_timeout(2400)
    undone = page.evaluate("() => window.trailsPlan.state().points.length")

    # The profile is one tap away rather than gone.
    page.evaluate("() => window.trailsChrome.open('profile')")
    page.wait_for_timeout(900)
    asked = page.evaluate(seen)

    page.evaluate("() => { document.querySelectorAll('.trails-planbar button')[1].click(); }")
    page.wait_for_timeout(900)
    done = page.evaluate(seen)

    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(900)

    return Check(
        "planning with the map still showing",
        [
            Reading("the bar stands while planning", bool(planning["bar"]), True),
            Reading("px it takes", planning["bar"]["h"] if planning["bar"] else 0, 44),
            # The whole point: the profile does not open by itself on a phone
            # while the reader is tapping the ground it would cover.
            Reading("and the profile does not open by itself", planning["profile"], None),
            Reading(
                "px of map left to tap on",
                planning["bar"]["top"] if planning["bar"] else 0,
                784,
                within=2,
                note="439 before",
            ),
            Reading("it says how far the walk has got", "point" in (planning["says"] or ""), True, note=planning["says"]),
            # NaN is neither null nor undefined, and a route of crossings alone
            # has no climb: driven on open water the bar once read "+NaN m".
            Reading("and never says NaN", "NaN" in (planning["says"] or ""), False),
            Reading("one tap reaches the list", reached["rows"] > 0, True, note=f"{reached['rows']} rows"),
            # **One place, one entry.** It read two until the history's own
            # function was renamed apart from the height cache's: a freehand
            # leg's heights arriving called what it thought was the cache and
            # was the history.
            Reading("one place is one change", pressable["steps"] - pressable["before the place"], 1),
            Reading("one tap undoes it", undone, before - 1),
            Reading("and leaves what was there", page.evaluate(laid), was),
            Reading("and the profile is one tap away", bool(asked["profile"]), True),
            Reading(
                "with the bar still above it",
                bool(asked["bar"] and asked["profile"] and asked["bar"]["top"] < asked["profile"]["top"]),
                True,
            ),
            Reading("done puts plan mode away", done["state"]["planning"], False),
            Reading("and the bar with it", done["bar"], None),
        ],
    )


def files_from_the_page(page: Any) -> Check:
    """Writing a file and reading one back, on a phone-sized page.

    **Only a browser can answer this.** The page builds a blob, offers it
    through an anchor it puts in the document, and reads a file back through an
    ``<input type="file">`` and a ``FileReader``; none of that exists in the
    source tests, and the archive is written by hand -- varints, deflate-raw and
    a DOS timestamp -- so *it opens* is a claim about arithmetic.

    It also catches a class of defect nothing else did. Driven before this check
    existed, a stage's file came out as
    ``lomsdal-visten-Planned-route-in-Lomsdal-Visten-1-2-1-2.gpx``: the file name
    fell back from ``stem`` to ``name``, ``name`` is the track's title, and the
    title already ends in the stage. 111 browser readings and 208 source tests
    were all green over it.

    Args:
        page: The driven page, at any state

    Returns:
        What came out, whether the archive opens, and what a round trip restored
    """
    import tempfile
    import zipfile

    # **It lays its own route down rather than inheriting one.** The checks
    # before this take points out -- one of them exists to prove that undo does
    # -- so a file check that used what it found would write whatever was left
    # and skip itself the day that was nothing.
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(900)
    page.evaluate("() => window.trailsChrome.close()")
    if not select(page, LONG_CHAIN):
        page.set_viewport_size({"width": 1400, "height": 900})
        return Check("files written and read back", skipped=f"{LONG_CHAIN} is not in this page")

    places = page.evaluate(
        """() => { const shape = window.trailsProfile.shape;
        return [0.08, 0.35, 0.62, 0.9].map(f => Math.floor(f * (shape.lon.length - 1)))
          .map(i => ({lat: shape.lat[i], lon: shape.lon[i]})); }"""
    )
    page.evaluate("() => window.trailsPlan.toggle(true)")
    page.wait_for_timeout(600)
    page.evaluate(
        """() => { const standing = window.trailsPlan.state().points.length;
        for (let i = 0; i < standing; i += 1) { window.trailsPlan.undo(); } }"""
    )
    page.wait_for_timeout(1200)
    for at in places:
        page.evaluate("(where) => window.trailsPlan.place(where.lat, where.lon)", at)
        page.wait_for_timeout(2000)
    page.wait_for_timeout(2500)

    page.evaluate("() => window.trailsChrome.open('profile')")
    page.wait_for_timeout(900)
    out = pathlib.Path(tempfile.mkdtemp(prefix="trails-drive-"))

    press_download = """() => { const panel = document.querySelector('.trails-profile-panel');
        [...panel.querySelectorAll('button')].find(b => /Download/.test(b.textContent)).click(); }"""
    with page.expect_download(timeout=25_000) as caught:
        page.evaluate(press_download)
    written = caught.value
    route = out / written.suggested_filename
    written.save_as(route)
    text = route.read_text(encoding="utf-8")

    # A stage, and the archive that gathers them.
    page.evaluate("() => { window.trailsPlan.showList(true); window.trailsChrome.open('plan'); }")
    page.wait_for_timeout(900)
    page.evaluate(
        """() => { const rows = [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage'));
        const cut = rows[1] && rows[1].querySelector('.trails-plan-cut');
        if (cut) { cut.click(); } }"""
    )
    page.wait_for_timeout(1600)
    members: list[str] = []
    broken: str | None = "the archive was never offered"
    if page.evaluate("() => { const z = document.querySelector('.trails-plan-zip'); return !!(z && z.offsetParent !== null); }"):
        with page.expect_download(timeout=35_000) as caught:
            page.evaluate("() => document.querySelector('.trails-plan-zip').click()")
        archive = out / caught.value.suggested_filename
        caught.value.save_as(archive)
        with zipfile.ZipFile(archive) as opened:
            broken = opened.testzip()
            members = opened.namelist()

    # And read one back, through the picker rather than around it.
    page.evaluate("() => { window.trailsPlan.toggle(false); window.trailsPlan.toggle(true); }")
    page.wait_for_timeout(700)
    page.set_input_files(".trails-plan-file", str(route))
    page.wait_for_timeout(3000)
    offer = page.evaluate("() => window.trailsPlan.state().pending")
    restored = None
    if offer:
        page.evaluate("() => window.trailsPlan.take()")
        page.wait_for_timeout(4500)
        restored = page.evaluate("() => window.trailsPlan.state().points.length")

    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(900)

    stages = [name for name in members if name != written.suggested_filename]
    return Check(
        "files written and read back",
        [
            Reading("a route downloads", written.suggested_filename.endswith(".gpx"), True, note=written.suggested_filename),
            Reading("and is a GPX", text.startswith('<?xml version="1.0" encoding="UTF-8"?>'), True),
            Reading("carrying its waypoints", text.count("<wpt ") > 0, True, note=f"{text.count('<wpt ')} wpt"),
            Reading("the archive opens", broken, None),
            Reading("holding a stage each and the tour", len(members), 3, note="; ".join(members)),
            # The defect this check exists for: a stage's file name must carry
            # the stage once. `stem` is the file's name and `name` is the
            # track's, and neither is the other's fallback.
            Reading(
                "and no stage names itself twice",
                all(name.count(name.rsplit("-", 2)[-2] + "-" + name.rsplit("-", 2)[-1]) == 1 for name in stages),
                True,
                note="; ".join(stages),
            ),
            Reading("a file picked with the picker is offered", bool(offer), True, note=str(offer["kind"]) if offer else ""),
            Reading("and taking it restores its points", restored, offer["waypoints"] if offer else None),
        ],
    )


def a_click_is_not_a_pan(page: Any) -> Check:
    """Placing a point by clicking the map, and not placing one by dragging it.

    **The path nothing else drove.** Every other check places a waypoint through
    ``window.trailsPlan.place``, which is the API and not the gesture: the
    dispatcher that tells a click on the ground from the end of a pan was
    covered by no reading at all. It matters now because what records where a
    gesture began moved from ``mousedown`` to ``pointerdown`` — a finger fires
    no ``mousedown`` of its own, and whether a browser sends a compatibility one
    after a pan was the assumption this replaced.

    The finger's own half cannot be driven: a synthetic ``TouchEvent`` produces
    no compatibility events, which is the mechanism in question. What is driven
    here is that the mouse's half did not move.

    Args:
        page: The driven page, at any state

    Returns:
        What a click placed and what a drag did not

    """
    page.evaluate("() => { window.trailsChrome.close(); window.trailsPlan.toggle(true); }")
    page.wait_for_timeout(700)
    # Removed rather than undone: undo steps back a change now, and a route
    # emptied by undoing would be emptied only where every change was a place.
    page.evaluate(
        """() => { const standing = window.trailsPlan.state().points.length;
        for (let i = 0; i < standing; i += 1) { window.trailsPlan.remove(0); } }"""
    )
    page.wait_for_timeout(1600)
    empty = page.evaluate("() => window.trailsPlan.state().points.length")

    middle = page.evaluate(
        """() => { const r = document.querySelector('.leaflet-container').getBoundingClientRect();
        return {x: Math.round(r.left + r.width * 0.55), y: Math.round(r.top + r.height * 0.42)}; }"""
    )
    page.mouse.click(middle["x"], middle["y"])
    page.wait_for_timeout(2400)
    clicked = page.evaluate("() => window.trailsPlan.state().points.length")

    # A pan ends in a click too, and how far the pointer travelled is what tells
    # the two apart -- measured from where the gesture began, which is what
    # pointerdown records.
    page.mouse.move(middle["x"] - 120, middle["y"] + 60)
    page.mouse.down()
    page.mouse.move(middle["x"] - 40, middle["y"] + 20, steps=8)
    page.mouse.up()
    page.wait_for_timeout(2000)
    panned = page.evaluate("() => window.trailsPlan.state().points.length")

    page.evaluate("() => window.trailsPlan.toggle(false)")
    page.wait_for_timeout(400)

    return Check(
        "a click places a point and a pan does not",
        [
            Reading("it starts with nothing down", empty, 0),
            Reading("a click on the ground places one", clicked, 1),
            Reading("and dragging the map places none", panned, clicked),
        ],
    )


def the_search_on_a_narrow_panel(page: Any) -> Check:
    """A field measured for a corner, standing in a panel.

    Measured before this: 210 px wide and 25 px tall in a 390 px sheet, so a
    third of the row was spent and the target was well under a finger. The width
    belongs to the dock -- it is the same field on any pointer -- and the height
    belongs to the pointer.

    **16 px of type is not a taste.** iOS Safari zooms the whole page when a
    field smaller than that takes focus, which on a map is the reader losing
    their place in order to type a name.

    Args:
        page: The driven page

    Returns:
        What the field measures at each width and with each pointer
    """
    read = """() => { const field = document.querySelector('.trails-search-field');
      if (!field || field.offsetParent === null) { return null; }
      const r = field.getBoundingClientRect();
      const dock = document.querySelector('.trails-dock').getBoundingClientRect();
      return {w: Math.round(r.width), h: Math.round(r.height),
              size: Math.round(parseFloat(getComputedStyle(field).fontSize)),
              share: Math.round(100 * r.width / dock.width)}; }"""

    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(900)
    page.evaluate("() => { window.trailsChrome.coarse(true); window.trailsChrome.open('search'); }")
    page.wait_for_timeout(700)
    finger = page.evaluate(read)

    page.evaluate("() => window.trailsChrome.coarse(null)")
    page.wait_for_timeout(500)
    mouse = page.evaluate(read)

    # And it finds what it always found.
    page.fill(".trails-search-field", "Gåsvatnet")
    page.wait_for_timeout(1200)
    found = page.evaluate(
        """() => { const box = document.querySelector('.trails-search');
        return (box.textContent.match(/(\\d+) match/) || [null, '0'])[1]; }"""
    )
    page.fill(".trails-search-field", "")
    page.evaluate("() => window.trailsChrome.close()")
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(900)

    return Check(
        "the search takes the row it is given",
        [
            Reading("with a finger: px tall", finger["h"] if finger else 0, 40, within=2, note="25 before"),
            Reading("and px of type", finger["size"] if finger else 0, 16),
            Reading("with a mouse: px tall", mouse["h"] if mouse else 0, 25, within=4),
            # The width is the dock's business and not the pointer's: it is the
            # same field either way, in the same panel.
            Reading("either way, per cent of the panel it takes", finger["share"] if finger else 0, 92, within=5, note="54 before"),
            Reading("and it still finds a name", int(found), 3, holds=False),
        ],
    )


def the_profile_tool(page: Any) -> Check:
    """A tool that is never dead, and says what it needs when it has nothing.

    Reported by a reader who met it on the published map: *what is profile? I
    cannot click it.* It was the only tool in the rail that was ever disabled --
    greyed at 0.4, with no reason given, and on the rail with no text at all --
    and *ever* meant every moment before something is selected, which is exactly
    when somebody meets it for the first time.

    **A control that cannot be used has to say why**, and here it can do better
    than that: it opens like every other tool and tells the reader what it draws
    and what it needs. It is also called what its own panel calls itself now.

    Args:
        page: The driven page, with nothing selected

    Returns:
        Whether it opens, what it says, and whether it gets out of the way
    """
    button = """() => { const b = document.querySelector('.trails-rail button[data-tool=profile]');
      return b ? {title: b.title, disabled: b.disabled, colour: b.style.color} : null; }"""
    shown = """() => { const open = [...document.querySelectorAll('.trails-chrome-body > div')]
        .filter(node => node.offsetParent !== null);
      const empty = document.querySelector('.trails-profile-empty');
      return {holders: open.length, empty: !!(empty && empty.offsetParent !== null),
              says: open.length === 1 ? open[0].textContent.trim().slice(0, 60) : ''}; }"""

    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(500)
    at_rest = page.evaluate(button)

    page.evaluate("() => window.trailsChrome.open('profile')")
    page.wait_for_timeout(700)
    opened = page.evaluate(shown)
    titled = page.evaluate("() => document.querySelector('.trails-dock .trails-chrome-title').textContent")

    told = select(page, LONG_CHAIN)
    page.wait_for_timeout(900)
    after = page.evaluate("() => ({tool: window.trailsChrome.state().tool, profile: window.trailsChrome.state().profile})")
    lit = page.evaluate(button)

    # **Folding is not hiding**, and the reading has to know which it asked
    # for: the panel's own heading collapses it to a 35 px bar and leaves it on
    # the map, which is what this tool does where there is room for it.
    tall = "() => { const p = document.querySelector('.trails-profile-panel'); return p ? Math.round(p.getBoundingClientRect().height) : 0; }"
    open_px = page.evaluate(tall)
    page.evaluate("() => window.trailsChrome.open('profile')")
    page.wait_for_timeout(600)
    folded_px = page.evaluate(tall)
    page.evaluate("() => window.trailsChrome.open('profile')")
    page.wait_for_timeout(600)

    # And it hands the page back the way it found it, or the check after this
    # one selects the same chain and deselects it instead.
    page.evaluate(SELECT_CHAIN, LONG_CHAIN)
    page.wait_for_timeout(900)

    return Check(
        "the elevation profile tool",
        [
            Reading("it is never disabled", at_rest["disabled"] if at_rest else True, False),
            Reading("and is called what its panel is called", at_rest["title"] if at_rest else "", "Elevation profile"),
            Reading("with nothing selected it opens", titled, "Elevation profile"),
            # One holder visible and one only: every tool's panel lives in the
            # dock from the start, hidden rather than detached, so "what is on
            # screen" is a question about display and not about the tree.
            Reading("showing exactly one panel", opened["holders"], 1),
            Reading("and it is the one that explains it", opened["empty"], True, note=opened["says"]),
            # The moment there is something to draw, a panel saying there is not
            # is a wrong sentence on the screen.
            Reading("selecting a trail takes it away", after["tool"] if told else None, None),
            Reading("and draws the profile instead", after["profile"] if told else True, True),
            Reading("the rail says the panel is standing", lit["colour"] if lit else "", "rgb(13, 71, 161)"),
            Reading("and the tool folds it away", folded_px < open_px / 2, True, note=f"{open_px} px to {folded_px}"),
            Reading("leaving nothing selected behind it", page.evaluate("() => window.trailsProfile"), None),
        ],
    )


def brushing_the_curve(page: Any) -> Check:
    """Press, drag, let go, and the panel draws what lay between the two.

    Driven with a **real mouse** — down, moved in steps, up — because a
    dispatched sequence would prove the arithmetic and not that a browser ever
    starts the gesture, which is the caveat this suite already carries about
    HTML5 dragging.

    The pointer was free for it: a plain drag did nothing at all at the whole
    chain, and moved the window only once a wheel had zoomed into something.
    Moving is not taken away for it, it moves to shift — taking a working
    gesture off a reader to avoid an overlap is not an improvement.

    Args:
        page: The driven page, with a zoomable chain selected

    Returns:
        What a drag picked, what a click did not, and what shift still does
    """
    view = "() => window.trailsProfilePanel.view()"
    rects = "() => document.querySelectorAll('.trails-profile-panel svg rect').length"
    reset = """() => { const chart = document.querySelector('.trails-profile-panel svg');
        chart.dispatchEvent(new MouseEvent('dblclick', {bubbles: true, cancelable: true})); }"""

    page.evaluate(reset)
    page.wait_for_timeout(600)
    whole = page.evaluate(view)
    at_rest = page.evaluate(rects)

    box = page.evaluate(
        """() => { const r = document.querySelector('.trails-profile-panel svg').getBoundingClientRect();
        return {left: r.left, top: r.top, w: r.width, h: r.height}; }"""
    )
    middle = box["top"] + box["h"] / 2

    def pick(first: float, last: float) -> dict:
        page.mouse.move(box["left"] + box["w"] * first, middle)
        page.mouse.down()
        page.mouse.move(box["left"] + box["w"] * (first + last) / 2, middle, steps=4)
        held = page.evaluate(rects)
        page.mouse.move(box["left"] + box["w"] * last, middle, steps=6)
        page.mouse.up()
        page.wait_for_timeout(700)
        return {"held": held, **page.evaluate(view)}

    picked = pick(0.35, 0.60)

    page.evaluate(reset)
    page.wait_for_timeout(600)
    again = pick(0.35, 0.60)

    # A click is a drag of nothing, and must stay one.
    before = page.evaluate(view)
    page.mouse.click(box["left"] + box["w"] * 0.5, middle)
    page.wait_for_timeout(600)
    clicked = page.evaluate(view)

    page.keyboard.down("Shift")
    page.mouse.move(box["left"] + box["w"] * 0.60, middle)
    page.mouse.down()
    page.mouse.move(box["left"] + box["w"] * 0.40, middle, steps=6)
    page.mouse.up()
    page.keyboard.up("Shift")
    page.wait_for_timeout(700)
    shifted = page.evaluate(view)

    page.evaluate(reset)
    page.wait_for_timeout(600)
    back = page.evaluate(view)

    return Check(
        "picking a stretch of the curve",
        [
            Reading("a rectangle is drawn while the button is held", picked["held"] - at_rest, 1),
            Reading("and is gone once it is let go", page.evaluate(rects), at_rest),
            # The window is inside the one it was picked from, and the zoom says
            # the same thing the width does: they are one number seen twice.
            Reading("what is shown is inside what was", picked["shown"] < whole["shown"], True),
            Reading(
                "and the zoom agrees with the width",
                round(whole["shown"] / picked["shown"], 2),
                round(picked["zoom"], 2),
                within=0.02,
            ),
            Reading("the same drag twice picks the same stretch", round(again["at"]), round(picked["at"])),
            Reading("a click picks nothing", round(clicked["at"]), round(before["at"])),
            Reading("and does not zoom", round(clicked["zoom"], 3), round(before["zoom"], 3)),
            # Moving did not go away for it.
            Reading("shift-drag keeps the zoom", round(shifted["zoom"], 3), round(clicked["zoom"], 3)),
            Reading("and moves the window", shifted["at"] != clicked["at"], True),
            Reading("a double click puts the whole chain back", round(back["zoom"], 3), 1.0),
            # A recorded figure: it moves when the chain or the panel does.
            Reading("m shown by a quarter-width drag", round(picked["shown"]), 11188, within=60, holds=False),
        ],
    )


def undo_undoes_the_last_change(page: Any) -> Check:
    """Taking back what was just done, whatever it was.

    Reported by a reader: a point placed on the leg between 5 and 6 became point
    6, and *Take back the last point* removed point 7 — the one that had been 6.
    Reproduced exactly. Until phase 7 every edit was an append and
    ``points.pop()`` **was** an undo; inserting, removing, reordering and
    dragging arrived and the button was never revisited, so it did the opposite
    of undoing on four of the five things a reader can do.

    The four cases below are the ones a pop can never get right: an insertion
    ends somewhere other than the end, a removal has to put something **back**,
    a reorder changes no count at all, and a stage mark changes no points.

    Args:
        page: The driven page, with a chain selected

    Returns:
        What each change did and what taking it back left behind
    """
    ids = "() => window.trailsPlan.state().points.map(p => Math.round(p.lat * 1e5) + '/' + Math.round(p.lon * 1e5))"

    # **Cleared by removing, not by undoing.** Undoing steps back a *change*
    # now, which is the whole point of this check — using it to empty the list
    # would be assuming the thing under test.
    page.evaluate(
        """() => { window.trailsChrome.close();
        const standing = window.trailsPlan.state().points.length;
        for (let i = 0; i < standing; i += 1) { window.trailsPlan.remove(0); } }"""
    )
    page.wait_for_timeout(1600)
    # **And plan mode goes off to pick the chain.** While it is on the panel
    # stops answering clicks -- the map's clicks are the plan's -- so selecting
    # a chain with it on selects nothing and every reading after that skips.
    page.evaluate("() => window.trailsPlan.toggle(false)")
    page.wait_for_timeout(500)
    if not select(page, LONG_CHAIN):
        return Check("undo undoes the last change", skipped=f"{LONG_CHAIN} is not in this page")
    places = page.evaluate(
        """() => { const shape = window.trailsProfile.shape;
        return [0.05, 0.3, 0.55, 0.8].map(f => Math.floor(f * (shape.lon.length - 1)))
          .map(i => ({lat: shape.lat[i], lon: shape.lon[i]})); }"""
    )
    page.evaluate("() => window.trailsPlan.toggle(true)")
    page.wait_for_timeout(500)
    for at in places:
        page.evaluate("(where) => window.trailsPlan.place(where.lat, where.lon)", at)
        page.wait_for_timeout(2000)
    page.wait_for_timeout(2500)
    laid = page.evaluate(ids)

    def take_back() -> Any:
        page.evaluate("() => window.trailsPlan.undo()")
        page.wait_for_timeout(2600)
        return page.evaluate(ids)

    # 1. an insertion, which is the case reported: it ends in the middle.
    between = page.evaluate(
        """() => { const shape = window.trailsProfile.shape;
        const stations = window.trailsPlan.state().stations;
        const target = (stations[1] + stations[2]) / 2;
        let best = 0, gap = Infinity;
        for (let i = 0; i < shape.along.length; i += 1) {
          const away = Math.abs(shape.along[i] - target);
          if (away < gap) { gap = away; best = i; } }
        return {lat: shape.lat[best], lon: shape.lon[best]}; }"""
    )
    page.evaluate("(where) => window.trailsPlan.insert(2, where.lat, where.lon)", between)
    page.wait_for_timeout(2600)
    inserted = page.evaluate(ids)
    after_insert = take_back()

    # 2. a removal, which a pop could never take back: it has to put one in.
    page.evaluate("() => window.trailsPlan.remove(1)")
    page.wait_for_timeout(2600)
    shorter = page.evaluate(ids)
    after_remove = take_back()

    # 3. a reorder, which changes no count at all.
    page.evaluate("() => window.trailsPlan.moveTo(3, 1)")
    page.wait_for_timeout(2600)
    reordered = page.evaluate(ids)
    after_move = take_back()

    # 4. a stage mark, which changes no points.
    page.evaluate("() => { window.trailsPlan.showList(true); window.trailsChrome.open('plan'); }")
    page.wait_for_timeout(900)
    pressed = page.evaluate(
        """() => { const rows = [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage'));
        const cut = rows[1] && rows[1].querySelector('.trails-plan-cut');
        if (!cut) { return 'no cut button on row 2 of ' + rows.length; }
        cut.click(); return 'pressed'; }"""
    )
    page.wait_for_timeout(1400)
    stages = page.evaluate("() => window.trailsPlan.state().points.filter(p => typeof p.stage === 'string').length")
    take_back()
    page.wait_for_timeout(600)
    stages_back = page.evaluate("() => window.trailsPlan.state().points.filter(p => typeof p.stage === 'string').length")

    # And it stops rather than eating the route when there is nothing left.
    drained = page.evaluate(
        """() => { for (let i = 0; i < 60; i += 1) { window.trailsPlan.undo(); }
        return window.trailsPlan.state().undoable; }"""
    )
    page.wait_for_timeout(2600)
    emptied = page.evaluate("() => window.trailsPlan.state().points.length")
    page.evaluate("() => { for (let i = 0; i < 5; i += 1) { window.trailsPlan.undo(); } }")
    page.wait_for_timeout(2000)
    still = page.evaluate("() => window.trailsPlan.state().points.length")
    page.evaluate("() => window.trailsPlan.toggle(false)")
    page.wait_for_timeout(400)

    return Check(
        "undo undoes the last change",
        [
            Reading("an insertion lands in the middle", len(inserted), len(laid) + 1),
            # The reported defect, exactly: the pop took the point that had been
            # renumbered rather than the one just placed.
            Reading("and taking it back leaves what was there", after_insert, laid),
            Reading("a removal takes one out", len(shorter), len(laid) - 1),
            Reading("and taking it back puts it back where it was", after_remove, laid),
            Reading("a reorder changes no count", len(reordered), len(laid)),
            Reading("and taking it back restores the order", after_move, laid),
            Reading("a stage mark is a change too", stages, 1, note=pressed),
            Reading("and taking it back unmarks it", stages_back, 0),
            # **Two readings and not one**, because they are different claims:
            # that the history drains, which is arithmetic and exact, and that
            # undoing past the end changes nothing, which is the guard. A
            # long shared session can leave one no-op entry behind that a run of
            # this check alone does not — measured, remembered with points still
            # down, and not explained. It costs a press that does nothing, so it
            # is written down rather than asserted away.
            Reading("draining it empties it", drained, 0),
            Reading("and the route with it", emptied, 0),
            Reading("and undoing past the end changes nothing", still, 0),
        ],
    )


# ---------------------------------------------------------------------------


def drive(page: Any) -> list[Check]:
    """Run every check in one browser session.

    Args:
        page: A page already loaded and settled

    Returns:
        Every check, in the order it ran
    """
    checks = [furniture(page), map_wheel(page), chrome_layout(page), the_profile_tool(page)]

    if not select(page, LONG_CHAIN):
        checks.append(Check("the profile panel", skipped=f"{LONG_CHAIN} is not in this page — see LONG_CHAIN"))
        return checks

    checks.append(sea_level(page))
    checks.append(crosshair_mark(page))
    checks.append(curve_wheel(page, zoomable=True))
    checks.append(true_scale(page))
    checks.append(zoom_ceiling(page))
    checks.append(brushing_the_curve(page))
    checks.append(pinch_the_curve(page))
    checks.append(a_way_back_to_the_whole(page))
    checks.append(room_on_a_short_screen(page))
    checks.append(narrow_sheets(page))
    select(page, LONG_CHAIN)

    # A chain already drawn finer than its own samples, which is 99 % of them:
    # there the wheel belongs to the map and the chart must not touch it.
    short = page.evaluate(
        """(long) => {
        for (const path of document.querySelectorAll('.leaflet-overlay-pane path')) {
          const cls = [...path.classList].find(c => c.indexOf('trail-group-') === 0);
          if (cls && cls !== long) { return cls; } }
        return null; }""",
        LONG_CHAIN,
    )
    if short and select(page, short):
        if page.evaluate("() => { const v = window.trailsProfilePanel.view(); return v && v.closest <= 1.001; }"):
            checks.append(curve_wheel(page, zoomable=False))

    select(page, LONG_CHAIN)
    places = page.evaluate(
        """() => { const shape = window.trailsProfile.shape;
        // Four positions along a real chain, so every leg has a network under it
        // and the route settles instead of failing.
        return [0.05, 0.3, 0.55, 0.8]
          .map(f => Math.floor(f * (shape.lon.length - 1)))
          .map(i => ({lat: shape.lat[i], lon: shape.lon[i]})); }"""
    )

    held = page.evaluate("() => window.trailsHighlight && window.trailsHighlight.selected()")
    page.evaluate(PLAN_TOGGLE)
    page.wait_for_timeout(800)
    checks.append(
        Check(
            "plan mode lets go of a highlighted line",
            [
                Reading("a line was highlighted first", held is not None, True),
                # Both of the highlight's own ways out are clicks, and plan mode
                # owns every click from the moment it is on.
                Reading("and is let go of", page.evaluate("() => window.trailsHighlight.selected()"), None),
            ],
        )
    )

    checks.append(popup_click(page))
    checks.append(stations_and_list(page, places))
    checks.append(a_finger_can_use_it(page))
    checks.append(the_plan_bar(page))
    checks.append(undo_undoes_the_last_change(page))
    checks.append(files_from_the_page(page))
    checks.append(a_click_is_not_a_pan(page))
    checks.append(the_search_on_a_narrow_panel(page))
    checks.append(sharing_the_room(page))
    return checks


def report(checks: list[Check]) -> int:
    """Print what was measured and say whether it holds.

    Args:
        checks: Every check that ran

    Returns:
        0 where everything holds, 1 where an invariant broke, 2 where only a
        recorded figure moved — which may be news rather than a fault
    """
    broke, moved, skipped = 0, 0, 0
    for check in checks:
        if check.skipped:
            skipped += 1
            print(f"\n  ?  {check.name}\n     skipped: {check.skipped}")
            continue
        print(f"\n     {check.name}")
        for reading in check.readings:
            mark = " ok " if reading.passed else ("FAIL" if reading.holds else "MOVED")
            if not reading.passed:
                broke += reading.holds
                moved += not reading.holds
            got = f"{reading.got:.6g}" if isinstance(reading.got, float) else reading.got
            said = f"       {mark:>5}  {reading.what}: {got}"
            if not reading.passed:
                said += f"   (expected {reading.want}" + (f" ± {reading.within}" if reading.within else "") + ")"
            if reading.note:
                said += f"   [{reading.note}]"
            print(said)

    print(
        f"\n{'-' * 72}\n"
        f"  {sum(len(c.readings) for c in checks)} readings, "
        f"{broke} broken invariant{'' if broke == 1 else 's'}, "
        f"{moved} recorded figure{'' if moved == 1 else 's'} moved, {skipped} skipped"
    )
    if moved and not broke:
        print(
            "  A moved figure is news, not necessarily a fault: the sources move and the\n"
            "  page moves with them. Look at why before changing the number here."
        )
    return 1 if broke else (2 if moved else 0)


def main() -> int:
    """Load the built page and drive it.

    Returns:
        The process's exit code
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--page", default=str(PAGE), help="The built map to drive")
    parser.add_argument("--headed", action="store_true", help="Show the browser rather than hiding it")
    parser.add_argument("--json", action="store_true", help="Print the readings as JSON as well")
    args = parser.parse_args()

    page_path = pathlib.Path(args.page)
    if not page_path.exists():
        print(f"no page at {page_path} — run `command make map` first", file=sys.stderr)
        return 1

    from playwright.sync_api import sync_playwright

    print(f"driving {page_path} ({page_path.stat().st_size / 1e6:.2f} MB)")
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        # **Everything this page does is in one script block**, so one syntax
        # error anywhere in it stops all of it -- and every check below then
        # fails at once, saying which behaviour is missing and never why. It
        # cost a build: a `\n` written into a template where `\\n` was meant
        # became a real line break inside a JavaScript string, and the whole map
        # was a blank grey box with 11,589 paths that never existed.
        thrown: list[str] = []
        page.on("pageerror", lambda error: thrown.append(str(error)))
        page.goto(page_path.resolve().as_uri())
        page.wait_for_timeout(SETTLE_MS)
        checks = [Check("the page ran at all", [Reading("errors thrown while loading", len(thrown), 0, note="; ".join(thrown[:2]))])]
        if thrown:
            browser.close()
            return report(checks)
        page.evaluate("() => window.trailsGraph.ready")
        checks += drive(page)
        browser.close()

    code = report(checks)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "check": c.name,
                        "skipped": c.skipped,
                        "readings": [
                            {"what": r.what, "got": r.got, "want": r.want, "within": r.within, "holds": r.holds, "passed": r.passed}
                            for r in c.readings
                        ],
                    }
                    for c in checks
                ],
                indent=1,
                default=str,
            )
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
