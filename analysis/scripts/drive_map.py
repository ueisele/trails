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
  return true; }""")

FURNITURE = with_map("""() => {
  const paths = [...document.querySelectorAll('.leaflet-overlay-pane path')];
  const legend = [...document.querySelectorAll('.leaflet-bottom.leaflet-left input')];
  const top = [...document.querySelectorAll('.leaflet-top.leaflet-left > div')]
    .map(node => Math.round(node.getBoundingClientRect().top));
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
    radios: legend.filter(i => i.type === 'radio').length,
    tiles: Object.values(__MAP__._layers).filter(l => l._url).length,
    controls: top.sort((a, b) => a - b),
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

PLAN_TOGGLE = "() => { document.querySelector('.trails-plan-control button').click(); }"

OPEN_LIST = """() => { const box = document.querySelector('.trails-plan-control');
  const handle = [...box.querySelectorAll('div')]
    .find(d => /point/.test(d.textContent) && d.style.cursor === 'pointer');
  if (handle) { handle.click(); } return !!handle; }"""

LIST_ROWS = """() => {
  const list = document.querySelector('.trails-plan-points');
  return list ? [...list.children].length : -1; }"""

DRAG_ROW = """(spec) => {
  const list = document.querySelector('.trails-plan-points');
  const from = list.children[spec.from], to = list.children[spec.to];
  if (!from || !to) { return false; }
  const data = new DataTransfer();
  const fire = (node, kind) => node.dispatchEvent(new DragEvent(kind,
    {bubbles: true, cancelable: true, dataTransfer: data}));
  fire(from, 'dragstart'); fire(to, 'dragover'); fire(to, 'drop'); fire(from, 'dragend');
  return true; }"""

REMOVE_ROW = """(at) => {
  const list = document.querySelector('.trails-plan-points');
  const row = list.children[at];
  if (!row) { return false; }
  row.querySelector('button').click(); return true; }"""

BOXES = """() => {
  const plan = document.querySelector('.trails-plan-control');
  const profile = document.querySelector('.trails-profile-panel');
  const seen = node => { const r = node.getBoundingClientRect();
    return {top: r.top, bottom: r.bottom, height: r.height}; };
  const a = seen(plan), b = seen(profile);
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
    if not page.evaluate(SELECT_CHAIN, chain):
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
    search, zoom = (seen["controls"] + [None, None])[:2]
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
            Reading("search box, px from the top", search, 10, within=1, holds=False),
            Reading("zoom buttons, px from the top", zoom, 60, within=1, holds=False),
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
    """A click inside a popup is not a click on the ground.

    Args:
        page: The driven page, in plan mode

    Returns:
        Whether the close button placed a waypoint, and whether it closed
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
        """() => { const popup = document.querySelector('.leaflet-popup');
        if (!popup) { return null; }
        const close = popup.querySelector('.leaflet-popup-close-button');
        const box = close.getBoundingClientRect();
        return {x: box.left + box.width / 2, y: box.top + box.height / 2}; }"""
    )
    if not where:
        return Check("a click in a popup", skipped="no popup opened")
    before = page.evaluate("() => window.trailsPlan.state().points.length")
    page.mouse.click(where["x"], where["y"])
    page.wait_for_timeout(1200)
    return Check(
        "a click in a popup is not a click on the ground",
        [
            Reading("waypoints placed by the close button", page.evaluate("() => window.trailsPlan.state().points.length") - before, 0),
            Reading("the popup closed", page.evaluate("() => !document.querySelector('.leaflet-popup')"), True),
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
                f"{label}: px of the plan control under the profile",
                round(seen["overlap"]),
                0,
                note=f"profile {seen['profile height']} px, list cap {seen['list cap']}",
            )
        )
        readings.append(Reading(f"{label}: the last row can still be reached", seen["last row reachable"], True, note=f"{seen['rows']} rows"))

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


# ---------------------------------------------------------------------------


def drive(page: Any) -> list[Check]:
    """Run every check in one browser session.

    Args:
        page: A page already loaded and settled

    Returns:
        Every check, in the order it ran
    """
    checks = [furniture(page), map_wheel(page)]

    if not select(page, LONG_CHAIN):
        checks.append(Check("the profile panel", skipped=f"{LONG_CHAIN} is not in this page — see LONG_CHAIN"))
        return checks

    checks.append(sea_level(page))
    checks.append(crosshair_mark(page))
    checks.append(curve_wheel(page, zoomable=True))
    checks.append(true_scale(page))
    checks.append(zoom_ceiling(page))

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
        page.goto(page_path.resolve().as_uri())
        page.wait_for_timeout(SETTLE_MS)
        page.evaluate("() => window.trailsGraph.ready")
        checks = drive(page)
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
