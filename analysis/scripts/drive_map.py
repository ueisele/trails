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
import contextlib
import functools
import http.server
import json
import math
import pathlib
import re
import sys
import threading
import time
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

#: Every drawn thing the map holds, whatever renderer drew it.
#:
#: **The map is drawn into a canvas now**, so `.leaflet-overlay-pane path`
#: reads 0 and one `<canvas>` where it used to read 11,589. The figures did not
#: move -- the same lines are drawn on the same map -- so they are read off the
#: map's own layers instead of off the elements a renderer happened to emit,
#: which is what they were always about.
#:
#: **A group's children are on the map in their own right.** `LayerGroup.onAdd`
#: hands every child to `map.addLayer`, so `map._layers` holds the group *and*
#: each leaf under it -- and a walk that recurses into groups counts every leaf
#: twice, which is how this first read 23,178 for 11,589. `eachLayer` is already
#: flat; the only thing to do is leave the groups out of it, and they answer
#: `setStyle` too because they forward it.
DRAWN = """
  const drawn = [];
  __MAP__.eachLayer(layer => { if (layer.setStyle && !layer.eachLayer) { drawn.push(layer); } });
  const chained = drawn.filter(l => (l.options.className || '').indexOf('trail-group-') === 0);
"""

WHOLE_MAP = with_map(
    """() => {"""
    + DRAWN
    + """ return {paths: drawn.length,
              markers: document.querySelectorAll('.leaflet-marker-pane > *').length,
              graph: !!(window.trailsGraph && window.trailsGraph.header)}; }"""
)
"""Everything the map holds, asked of the online page and of the offline one.

**The same question to both, so the answer can be compared between them rather
than against a number written down here.** What the offline check is for is that
the map opens *whole* with the network off -- every line, every marker, the
routing graph -- and *whole* means "what the same build drew a moment ago with
the network on". A recorded count says that only until the sources move, and then
it fails for the one reason that is not a fault: somebody cleared the cache and
regenerated the map, which is a thing this project does on purpose.
"""


FURNITURE = with_map(
    """() => {"""
    + DRAWN
    + """
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
  const frame = document.querySelector('.leaflet-container').getBoundingClientRect();
  const fromRight = node => node ? Math.round(frame.right - node.getBoundingClientRect().right) : null;
  return {
    paths: drawn.length,
    // A chain drawn as a line, and a chain drawn as a circle marker: 298 of
    // these chains are short enough to be drawn as a dot. Both carry a chain
    // class, which is why counting the class alone gives 11,588 and not the
    // 11,290 the decomposition in the notes names. A circle marker is the one
    // that can say how big it is.
    lines: chained.filter(l => !l.getRadius).length,
    circles: chained.filter(l => l.getRadius).length,
    loose: drawn.length - chained.length,
    // The park boundary, which opts out of the pointer so that a click reaches
    // the trails under its fill. Under canvas that is the option itself and no
    // longer a computed style.
    deaf: drawn.filter(l => l.options.interactive === false).length,
    markers: document.querySelectorAll('.leaflet-marker-pane > *').length,
    boxes: legend.filter(i => i.type === 'checkbox').length,
    off: legend.filter(i => i.type === 'checkbox' && !i.checked).length,
    radios: bases.filter(i => i.type === 'radio').length,
    tiles: Object.values(__MAP__._layers).filter(l => l._url).length,
    // The rail takes the top-left corner and the zoom steps aside for it. Left
    // rather than top, because both stand at 10 from the top and only the one
    // that moved says whether the corner made room.
    // The rail is measured from the *right* and the zoom from the left,
    // because that is the corner each of them keeps: the rail is in the one the
    // burger already had, and Leaflet's is Leaflet's again.
    controls: [fromRight(rail), at(zoom)],
    scaleBars: document.querySelectorAll('.leaflet-control-scale-line').length,
    // **The touch icon, fetched rather than read off the tag.** iOS takes this
    // one and ignores the manifest's, and the page carried it as a `data:` URI
    // for months -- a link that is present, well-formed, and one Safari will not
    // fetch, so the home screen showed a screenshot. A link that resolves to
    // nothing looks exactly the same in the markup.
    touchIcon: (document.querySelector('link[rel="apple-touch-icon"]') || {}).getAttribute
      ? document.querySelector('link[rel="apple-touch-icon"]').getAttribute('href') : null,
    // Asked of the browser and not of the stylesheet: `!important` against a
    // third party's rule is exactly the kind of override that can lose, and
    // losing it looks like a slightly blurred number rather than an error.
    scaleShadow: (() => {
      const bar = document.querySelector('.leaflet-control-scale-line');
      return bar ? getComputedStyle(bar).textShadow : null;
    })(),
    // A tool whose icon is missing is an error nowhere: `icon()` builds an
    // `<svg>` around `undefined`, so the row goes out with a blank column and
    // nothing anywhere says so. Counting the strokes is what notices.
    offlineStrokes: document.querySelectorAll('.trails-rail [data-tool=offline] svg path').length,
    layerControls: document.querySelectorAll('.leaflet-control-layers').length}; }"""
)

# The scale, read so that neither axis takes part in proving the other: the
# horizontal comes off the distance marks the axis draws, that names which
# sample the crosshair dot sits on, and the vertical falls out of its height.
SCALE = """() => {
  const svg = document.querySelector('.trails-profile-chart');
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
  const chart = document.querySelector('.trails-profile-chart');
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
  const svg = document.querySelector('.trails-profile-chart');
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
  const svg = document.querySelector('.trails-profile-chart');
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


#: Set by ``--only``. Empty means every check runs, which is what a full read of
#: the page is; a word in it runs the checks whose name contains that word.
ONLY = ""


def wanted(check: Any) -> bool:
    """Whether a check is one this run was asked for.

    **Iterating on one behaviour should not cost every other.** A full run loads
    a 40 MB page and drives twenty-odd checks; while a single one is being
    written that is three minutes to see one line. The checks left out are not
    reported at all rather than reported as skipped: a skip means *this could not
    be driven*, and "you did not ask for it" is a different sentence.

    Args:
        check: The function about to be called

    Returns:
        Whether to run it
    """
    return not ONLY or ONLY in check.__name__


def settled(page: Any, within_ms: int = 25_000) -> None:
    """Wait until plan mode has finished working, rather than until a clock says so.

    **The rule this suite states about itself and stopped keeping.** ``select``
    says it in as many words: the panel answers a microtask or more after the
    click, so a fixed pause is a guess that is too long on a fast machine and
    too short on a slow one. Every check added after it carried two- and
    three-second sleeps behind each edit — **109 of them, two minutes of a
    three-minute run** — while a leg usually settles in a fraction of one.

    Args:
        page: The driven page
        within_ms: How long to allow before giving up, which is a real failure
            and not a slow machine: nothing here takes twenty-five seconds.
    """
    page.wait_for_function("() => !window.trailsPlan || !window.trailsPlan.busy()", timeout=within_ms)


SHOW_TOOL = """(key) => { if (window.trailsChrome.state().tool !== key) { window.trailsChrome.open(key); } }"""
"""Open a tool and only if it is not the one already open.

**`open` is a toggle**, and a check that presses it blind measures the opposite
of what it asked for. That used to be hidden: docking a popup cleared the open
tool outright, so a tool was reliably shut before any of these ran. It is not
cleared any more -- a reader who closes the detail wants back what they had --
and six readings turned red at once, all of them measuring a panel that had just
been closed by the line meant to open it.
"""


def furniture(page: Any) -> Check:
    """What the page draws before anything is clicked.

    Args:
        page: The driven page

    Returns:
        The counts, against what the last build measured
    """
    seen = page.evaluate(FURNITURE)
    rail_right, zoom = (seen["controls"] + [None, None])[:2]
    return Check(
        "the page's furniture",
        [
            # Re-recorded 2026-09-01, from 11,589 and 11,290: the source cache
            # was cleared and the map regenerated, so Turrutebasen was fetched
            # again and came back with twelve more chains. This is the movement
            # a `stands` reading is for -- looked at, understood, written down.
            Reading("paths in the overlay pane", seen["paths"], 11601, holds=False),
            Reading("of them chains drawn as lines", seen["lines"], 11302, holds=False),
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
            # **One bar and not two.** A bare `L.control.scale()` draws metric
            # and imperial, one above the other, and with the zoom line under
            # them that corner reads as the same control drawn twice.
            Reading("bars in the scale control", seen["scaleBars"], 1),
            Reading("the touch icon is a file, not a data: URI", seen["touchIcon"], "icon-180.png"),
            Reading("and the figures drawn once, not twice", seen["scaleShadow"], "none"),
            Reading("strokes in the offline tool's drawing", seen["offlineStrokes"] > 0, True, note=f"{seen['offlineStrokes']} paths"),
            # **The rail takes the right and Leaflet keeps the left.** It stood
            # at the left and the chrome pushed Leaflet's whole top-left corner
            # 56 px aside for it — which put the zoom at 66, exactly where the
            # dock opens, so every tool a reader opened covered the zoom. The
            # rail is now in the corner the burger already has, and the zoom is
            # back at the 10 Leaflet gives it.
            Reading("the tool rail, px from the right", rail_right, 10, within=1),
            Reading("zoom buttons, px from the left", zoom, 10, within=1),
        ],
    )


def the_icons_are_there(page: Any) -> Check:
    """The four files the page and its manifest link to, fetched.

    **Because a link is not a file.** The page links to `icon-180.png` and the
    manifest to `icon-192.png` and `icon-512.png`; whether the build wrote them
    and the deploy carried them is a different question from whether the markup
    names them, and only one of the two shows up on a home screen.

    Args:
        page: The driven page

    Returns:
        What each icon answered, and what it turned out to be
    """
    got = page.evaluate(
        """async () => {
            const out = {};
            for (const name of ['icon-32.png', 'icon-180.png', 'icon-192.png', 'icon-512.png']) {
                try {
                    const answer = await fetch(name);
                    const bytes = new Uint8Array(await answer.arrayBuffer());
                    // The PNG signature, so a 404 page served as an image cannot pass.
                    const png = bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
                    out[name] = {ok: answer.ok, png: png, bytes: bytes.length};
                } catch (missing) { out[name] = {ok: false, png: false, bytes: 0}; }
            }
            return out;
        }"""
    )
    readings = []
    for name, answer in got.items():
        readings.append(Reading(f"{name} is a PNG that answers", bool(answer["ok"] and answer["png"]), True, note=f"{answer['bytes']} B"))
    return Check("the icons the page links to", readings)


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
        """() => { const chart = document.querySelector('.trails-profile-chart');
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
        settled(page)
    settled(page)
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
        settled(page)
        after = page.evaluate("() => window.trailsPlan.state().points.map(p => Math.round(p.lat * 1e6))")
        # A splice and not a swap: the dragged point is taken out and put back
        # in, and everything it passed shifts one place the other way.
        readings.append(Reading("dragging row 4 onto row 2 splices", after, [before[0], before[3], before[1], before[2]]))

    was = page.evaluate("() => window.trailsPlan.state().points.length")
    if page.evaluate(REMOVE_ROW, 1):
        settled(page)
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
      const chart = document.querySelector('.trails-profile-chart');
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
    reset = """() => { const chart = document.querySelector('.trails-profile-chart');
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


THEME_SWITCH = """() => {
  const root = document.documentElement;
  const chrome = document.querySelector('.trails-chrome');
  const ink = () => getComputedStyle(chrome).color;
  // **The labels and not a background rect.** The chart paints no rect -- its
  // paper colour goes on the crosshair's disc, which is only there while a
  // finger is on the curve. The axis labels carry `fill` as an attribute and
  // are drawn on every render, which is exactly the property under test.
  const paper = () => {
    const texts = [...document.querySelectorAll('.trails-profile-panel svg text')];
    return texts.length ? texts.map(t => t.getAttribute('fill')).join(',') : null;
  };
  const press = key => {
    const button = document.querySelector('.trails-theme-choice[data-theme-choice="' + key + '"]');
    if (!button) { return false; }
    button.click();
    return true;
  };
  const kept = () => { try { return window.localStorage.getItem('trails:theme'); } catch (blocked) { return 'denied'; } };

  const out = {buttons: document.querySelectorAll('.trails-theme-choice').length};
  out.pressed = ['auto', 'light', 'dark'].every(press);

  press('light');
  out.lightStamp = root.getAttribute('data-theme');
  out.lightInk = ink();
  out.lightPaper = paper();

  press('dark');
  out.darkStamp = root.getAttribute('data-theme');
  out.darkInk = ink();
  out.darkPaper = paper();
  out.darkKept = kept();

  press('auto');
  out.autoStamp = root.getAttribute('data-theme');
  out.autoKept = kept();
  out.autoSays = (document.querySelector('.trails-theme-state') || {}).textContent || '';
  return out;
}"""
"""What the switch does to the document, measured in the document.

The source tests can prove the three buttons are written and that `set` stamps
the root. Only a browser can say that the stamp actually repaints the furniture,
because that is CSS resolving a custom property -- and only a browser can say
whether the curve, which is painted with attributes instead, came with it.
"""


def the_theme_switch(page: Any) -> Check:
    """Auto, light and dark, and whether the page turns with them.

    **The curve is the reading that matters here.** Everything else on the page
    is painted through CSS and follows the stamp on its own; the elevation panel
    draws with SVG attributes read at stroke time, so it can be left behind in
    the old set by a switch that visibly worked everywhere else. That is a defect
    with no symptom in the source and an obvious one on the screen.

    Args:
        page: The driven page

    Returns:
        What each choice stamped, and what the page then drew
    """
    # **A chain is selected first, or the reading that matters is not taken.**
    # The curve is only drawn while something is on it, and a check that quietly
    # reports *not showing* for the one thing it was written for is a check that
    # passes by not looking.
    select(page, LONG_CHAIN)
    page.wait_for_timeout(700)
    page.evaluate(SHOW_TOOL, "theme")
    page.wait_for_timeout(300)
    seen = page.evaluate(THEME_SWITCH)
    readings = [
        Reading("choices offered", seen["buttons"], 3),
        Reading("every one of them presses", seen["pressed"], True),
        Reading("light stamps the root", seen["lightStamp"], "light"),
        Reading("dark stamps the root", seen["darkStamp"], "dark"),
        # **Auto is the absence of a stamp**, not the word. `data-theme="auto"`
        # would match neither the light block nor the dark one and leave the
        # reader in whichever came first.
        Reading("auto stamps nothing", seen["autoStamp"], None),
        Reading("and keeps nothing either", seen["autoKept"], None),
        Reading("dark is kept on the device", seen["darkKept"], "dark"),
        # The furniture actually turns: this is CSS resolving the custom
        # property, which is the half a source test cannot reach.
        Reading("the ink moves with it", seen["darkInk"] != seen["lightInk"], True, note=f"{seen['lightInk']} to {seen['darkInk']}"),
        Reading("auto says which way it falls", "Following this machine" in seen["autoSays"], True),
    ]
    if seen["lightPaper"] is not None:
        readings.append(
            Reading(
                "and the curve is redrawn with it", seen["darkPaper"] != seen["lightPaper"], True, note=f"{seen['lightPaper']} to {seen['darkPaper']}"
            )
        )
    else:
        readings.append(Reading("the curve is drawn at all", False, True, note=f"no labels found for {LONG_CHAIN}"))
    # **Left as it was found.** On a narrow screen an open tool covers the map,
    # and the checks after this one click into it. The choice is already back on
    # auto with nothing kept; this puts the panel away too.
    page.evaluate("() => window.trailsChrome.close()")
    return Check("the theme switch", readings)


def the_sources_behind_an_i(page: Any) -> Check:
    """Eleven lines of licence, and the room they take on a phone.

    Reported with a screenshot: on a phone held upright the sources fill more of
    the profile panel than the curve does. They were already folded behind an
    *i* -- but the rule was written from a measurement taken with the phone held
    sideways, so it asked about the height alone and a portrait screen is not
    short. It is the same lack of room measured on the other axis.

    What the *i* opens is the sheet a popup docks into and not eleven lines
    unfolded into the drawing: a page whose popups all dock into one panel has
    somewhere to put this.

    Args:
        page: The driven page, with a chain selected

    Returns:
        What the row shows narrow, what the *i* opens, and what it shows wide
    """
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(900)
    page.evaluate("() => window.trailsChrome.close()")
    if not select(page, LONG_CHAIN):
        page.set_viewport_size({"width": 1400, "height": 900})
        return Check("the sources behind an i", skipped=f"{LONG_CHAIN} is not in this page")
    page.wait_for_timeout(700)

    # `getClientRects()` and not `offsetParent`: the second is the probe this
    # suite has already been lied to by once.
    row = """() => {
      const box = sel => { const node = document.querySelector(sel);
        return node ? {drawn: node.getClientRects().length > 0, text: node.textContent} : null; };
      const head = document.querySelector('.trails-profile-head');
      return {more: box('.trails-profile-more'), licences: box('.trails-profile-licences'),
              ground: box('.trails-profile-ground'),
              hide: box('.trails-profile-hide'),
              summary: (document.querySelector('.trails-profile-figures') || {}).textContent || null}; }"""
    narrow = page.evaluate(row)

    page.evaluate("() => document.querySelector('.trails-profile-more').click()")
    page.wait_for_timeout(700)
    sheet = page.evaluate(
        """() => { const node = document.querySelector('.trails-detail');
        const said = node ? node.textContent : '';
        // **The sheet is built at the moment it is asked for**, so its blocks
        // exist only in a browser: a typo in the one that draws the colours
        // would be invisible to every source test and to a green build alike.
        const key = node ? node.querySelector('.trails-profile-key') : null;
        return {drawn: !!node && node.getClientRects().length > 0,
                text: said,
                ground: said.indexOf('The ground this covers'),
                sources: said.indexOf('Sources and licences'),
                colours: said.indexOf('How the curve is coloured'),
                bands: key ? key.children.length : 0,
                state: window.trailsChrome.state().detail}; }"""
    )

    # **What it covers, it gives back.** Reported: pressing the *i* took the plan
    # panel away and closing the sheet gave back nothing — the chrome cleared the
    # open tool outright, which is right when a tap on the ground answers the map
    # and wrong for a panel's own button. And a second press closes it, which is
    # what a button that opened something is expected to do.
    page.evaluate("() => window.trailsChrome.close()")
    page.evaluate(SHOW_TOOL, "plan")
    page.wait_for_timeout(700)
    drawn = """() => { const seen = sel => { const node = document.querySelector(sel);
        return !!node && node.getClientRects().length > 0; };
      return {dock: seen('.trails-dock'), sheet: seen('.trails-detail'),
              tool: window.trailsChrome.state().tool,
              detail: window.trailsChrome.state().detail}; }"""
    page.evaluate("() => document.querySelector('.trails-profile-more').click()")
    page.wait_for_timeout(700)
    over = page.evaluate(drawn)
    page.evaluate("() => document.querySelector('.trails-profile-more').click()")
    page.wait_for_timeout(700)
    back = page.evaluate(drawn)

    page.evaluate("() => window.trailsChrome.close()")
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(900)
    wide = page.evaluate(row)

    licences = (narrow["licences"] or {}).get("text") or ""
    return Check(
        "the sources behind an i",
        [
            Reading("the i is offered on a narrow screen", narrow["more"]["drawn"], True),
            Reading("and the licences are not in the panel", narrow["licences"]["drawn"], False),
            Reading("nor what ground the file covers", narrow["ground"]["drawn"], False),
            # The room this gives back is the whole point, and it is the
            # sentence itself that is long. This is a chain's own list, which is
            # the short case: the panel that was reported was a planned route
            # drawing on seven sources, and that names them in some 300
            # characters over eleven lines of a 390 px screen.
            Reading("what was taking the room", len(licences), 65, within=40, holds=False, note="characters, and a chain's list is the short one"),
            Reading("the i opens the sheet", sheet["drawn"], True),
            Reading("and the chrome says so", sheet["state"], True),
            Reading("headed as what it is", "Sources and licences" in sheet["text"], True),
            # **The order is the argument.** What a walk covers is about this
            # route, who may be asked about it is about the file, and the colour
            # key is the only thing in the sheet that says nothing about this
            # route at all -- it explains a drawing rule that holds for every
            # walk there will ever be, so it goes last.
            Reading("the ground comes before the sources", sheet["ground"] < sheet["sources"], True),
            Reading("and the colours after both", sheet["colours"] > sheet["sources"], True),
            # **Four, and the fifth is right to be missing.** The dashed line
            # is drawn only where something in the panel is dashed, and a chain
            # is never drawn straight across anything -- the rule the panel's own
            # key has kept since phase 4, now kept in the sheet as well. Asking
            # for five here was the check being wrong about the page.
            Reading("with a line for each band", sheet["bands"], 4),
            # And what the file would hold, which used to sit beside the button.
            Reading("and the count the button used to carry", "points" in sheet["text"], True),
            # The same sentence and not a second derivation of it: it is read off
            # the element that shows it.
            Reading("holding the licences themselves", licences in sheet["text"], True),
            # And the figures the heading dropped, in the same order it kept the
            # first three of.
            Reading("and every figure with them", "high " in sheet["text"] and "low " in sheet["text"], True),
            # The other switch in the heading, which is proposal one's.
            Reading("the × is offered beside it", narrow["hide"]["drawn"], True),
            # It covers the plan panel and does not dismiss it.
            Reading("the plan panel is still open under it", over["tool"], "plan"),
            Reading("covered, not closed", over["sheet"] and not over["dock"], True),
            # A second press closes the sheet, and the panel comes back.
            Reading("a second press closes it", back["detail"], False),
            Reading("and the plan panel is back", back["dock"], True),
            # **And a wide screen is no different now.** The rule used to be
            # about room — first height, then width — and the room was never
            # what made a 300-character list of licences the wrong thing to put
            # above a drawing. The heading carries three figures everywhere and
            # the *i* carries the rest everywhere.
            Reading("a wide screen is the same", wide["licences"]["drawn"], False),
            Reading("and the i is offered there too", wide["more"]["drawn"], True),
            # The three the heading keeps, on both: how far, how much climb, how
            # steep at worst.
            Reading("the heading is three figures", (wide["summary"] or "").count(" \u00b7 "), 2, note=wide["summary"] or ""),
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
    # **And the i no longer unfolds them into the drawing.** It did, and that
    # was the answer while the profile panel was the only place this page had to
    # put a sentence; there is a sheet now, and eleven lines unfolded into a
    # 390 px drawing gives straight back the room this check exists to protect.
    page.evaluate("() => document.querySelector('.trails-profile-more').click()")
    page.wait_for_timeout(600)
    opened = page.evaluate(parts)
    opened_sheet = page.evaluate(
        """() => { const node = document.querySelector('.trails-detail');
        return !!node && node.getClientRects().length > 0 && /CC BY|ODbL|CC0/.test(node.textContent); }"""
    )
    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(400)

    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(1200)
    desk = page.evaluate(parts)

    return Check(
        "a short screen gets its drawing back",
        [
            Reading("sideways: the licences are folded", folded["more"], True),
            # **Not a shorter row: no row.** It folded to 33 px behind an *i*;
            # with a sheet to put it in there is nothing left in the panel at all,
            # and the pixels go to the map rather than to a drawing that cannot
            # use them -- 111 metres to the pixel on a route this long, where the
            # width binds and extra height draws nothing at all.
            Reading("sideways: px the row takes", folded["meta"], 0),
            # And the freed pixels go to the drawing rather than to the map:
            # the share is on the chart while the furniture is what it costs, so
            # shrinking the furniture without moving the share gives the map the
            # room and the curve none of it.
            Reading("and the drawing gets them", folded["chart"], 109, within=6, note="78 px before"),
            Reading("and the panel is what is left", folded["panel"], 152, within=6, holds=False, note="of 390, against 195 before"),
            # Nothing is withheld: the sentence a reader has to see before
            # pressing Download is one tap away and says so.
            Reading("the i opens them in the sheet", opened_sheet, True),
            # And the row it was folded out of stays folded: the sentence a
            # reader has to see before pressing Download is one tap away, and
            # the drawing keeps its pixels while they read it.
            Reading("and the panel keeps its room", opened["meta"], folded["meta"], note=f"{opened['meta']} px"),
            # **The i is offered on a desktop too now.** The heading carries
            # three figures on every screen and everything else is behind it:
            # what was a width rule is not one any more.
            Reading("desktop: the i is there too", desk["more"], True),
            Reading("desktop: px the row takes", desk["meta"], 0),
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
    page.evaluate(SHOW_TOOL, "plan")
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
      // **The one that is drawn, not the first in the document.** Every row
      // holds these now and all but one row's are in a shut menu, so
      // `querySelector` answers with a button nobody can see.
      const shown = sel => { const all = [...document.querySelectorAll(sel)];
        return all.find(n => n.offsetParent !== null) || all[0] || null; };
      return {row: size(rows[0]),
              out: size(shown('.trails-plan-out')),
              up: size(shown('.trails-plan-up')),
              more: size(shown('.trails-plan-more')),
              grip: size(shown('.trails-plan-grip')),
              rows: rows.length}; }"""

    fine = page.evaluate(sizes)
    page.evaluate("() => window.trailsChrome.coarse(true)")
    page.wait_for_timeout(500)
    coarse = page.evaluate(sizes)

    # **The edits live in the row's own menu now**, so they are measured with
    # one open: closed, they are in the document and drawn nowhere, which is the
    # right answer to *how big is that target* and not a useful one.
    page.evaluate(
        """() => { const rows = [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage'));
        const more = rows[2] && rows[2].querySelector('.trails-plan-more');
        if (more) { more.click(); } }"""
    )
    page.wait_for_timeout(500)
    menu = page.evaluate(sizes)

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
    settled(page)
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
            # The row carries one target now and the rest are lines in its menu.
            Reading("coarse: the ⋯ is at least 40 px", min(coarse["more"] or [0, 0]) >= 40, True, note=str(coarse["more"])),
            Reading("coarse: a menu line is at least 40 px", (menu["out"] or [0, 0])[1] >= 40, True, note=str(menu["out"])),
            Reading("coarse: and the arrows with it", (menu["up"] or [0, 0])[1] >= 40, True, note=str(menu["up"])),
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
      const chart = document.querySelector('.trails-profile-chart');
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
      const chart = document.querySelector('.trails-profile-chart');
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
    settled(page)
    before = page.evaluate("() => window.trailsPlan.state().points.length")
    pressable = page.evaluate(
        """() => { const b = document.querySelector('.trails-planbar-undo');
        return {there: !!(b && b.offsetParent !== null), off: b ? b.disabled : null,
                steps: window.trailsPlan.state().undoable}; }"""
    )
    pressable["before the place"] = steps_before
    # **By name and not by position.** These were `button[0]` and `button[1]`,
    # and the day the bar grew a third button every one of these readings moved
    # by one: undo pressed the profile switch, Done pressed undo, and four
    # readings failed saying nothing about what had changed.
    page.evaluate("() => { document.querySelector('.trails-planbar-undo').click(); }")
    settled(page)
    undone = page.evaluate("() => window.trailsPlan.state().points.length")

    # The profile is one tap away rather than gone.
    page.evaluate(SHOW_TOOL, "profile")
    page.wait_for_timeout(900)
    asked = page.evaluate(seen)

    # The switch on the bar, pressed twice: away and back.
    bar_switch = {"there": page.evaluate("() => !!document.querySelector('.trails-planbar-profile')")}
    page.evaluate("() => { document.querySelector('.trails-planbar-profile').click(); }")
    page.wait_for_timeout(700)
    bar_switch["after"] = page.evaluate(seen)["profile"]
    page.evaluate("() => { document.querySelector('.trails-planbar-profile').click(); }")
    page.wait_for_timeout(700)
    bar_switch["again"] = page.evaluate(seen)["profile"]

    page.evaluate("() => { document.querySelector('.trails-planbar-done').click(); }")
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
            # From the bar itself, which is the tap: the rail is behind the
            # burger while planning, so the way to the curve was three taps
            # through a menu that is not about planning.
            Reading("the bar carries the switch", bar_switch["there"], True),
            Reading("and one tap on it puts the curve away", bar_switch["after"], None),
            Reading("and another brings it back", bar_switch["again"] is not None, True),
            Reading(
                "with the bar still above it",
                bool(asked["bar"] and asked["profile"] and asked["bar"]["top"] < asked["profile"]["top"]),
                True,
            ),
            Reading("done puts plan mode away", done["state"]["planning"], False),
            Reading("and the bar with it", done["bar"], None),
        ],
    )


def the_point_list_takes_the_room(page: Any) -> Check:
    """A list of waypoints on a screen that has room for them.

    Reported: scrolling over the waypoints zooms the map, and the rows are a
    scroller although there is room below. One cause. The list was capped at
    220 px whatever the screen, so a twelve-point route scrolled inside a panel
    with 350 px of room under it -- and running off the end of that scroller is
    what handed the wheel to the map, because the panel gave the turn up as soon
    as it had nothing left to scroll.

    **A wheel that started over a panel does not end in a zoom.** Each scroller
    inside takes what it can use; the outermost panel swallows the rest.

    Args:
        page: The driven page, at any state

    Returns:
        What the list measures, whether it has to scroll, and what the wheel did
    """
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(600)
    page.evaluate("() => { window.trailsChrome.close(); window.trailsPlan.toggle(false); }")
    page.wait_for_timeout(500)
    if not select(page, LONG_CHAIN):
        return Check("the point list takes the room", skipped=f"{LONG_CHAIN} is not in this page")
    places = page.evaluate(
        """() => { const shape = window.trailsProfile.shape;
        return [0.05, 0.14, 0.23, 0.32, 0.41, 0.5, 0.59, 0.68, 0.77, 0.86]
          .map(f => Math.floor(f * (shape.lon.length - 1)))
          .map(i => ({lat: shape.lat[i], lon: shape.lon[i]})); }"""
    )
    page.evaluate("() => window.trailsPlan.toggle(true)")
    page.wait_for_timeout(600)
    page.evaluate(
        """() => { const standing = window.trailsPlan.state().points.length;
        for (let i = 0; i < standing; i += 1) { window.trailsPlan.remove(0); } }"""
    )
    settled(page)
    for at in places:
        page.evaluate("(where) => window.trailsPlan.place(where.lat, where.lon)", at)
        settled(page)
    settled(page)
    page.evaluate("() => window.trailsPlan.showList(true)")
    page.evaluate(SHOW_TOOL, "plan")
    page.wait_for_timeout(1000)

    listed = page.evaluate(
        """() => { const rows = document.querySelector('.trails-plan-points');
        const seen = getComputedStyle(rows);
        return {h: Math.round(rows.getBoundingClientRect().height),
                cap: Math.round(parseFloat(seen.maxHeight)),
                over: rows.scrollHeight - rows.clientHeight,
                rows: [...rows.children].length}; }"""
    )

    # A wheel over the rows, at the far end of whatever they can scroll, which is
    # where the panel used to give the turn to the map.
    zoom = "() => window[Object.keys(window).find(k => k.startsWith('map_'))].getZoom()"
    before = page.evaluate(zoom)
    page.evaluate("() => { const rows = document.querySelector('.trails-plan-points'); rows.scrollTop = rows.scrollHeight; }")
    where = page.evaluate(
        """() => { const box = document.querySelector('.trails-plan-points').getBoundingClientRect();
        return {x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2)}; }"""
    )
    page.mouse.move(where["x"], where["y"])
    page.mouse.wheel(0, 320)
    page.wait_for_timeout(700)
    page.mouse.wheel(0, -320)
    page.wait_for_timeout(700)
    after = page.evaluate(zoom)

    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(400)

    return Check(
        "the point list takes the room",
        [
            Reading("ten points make ten rows", listed["rows"], 10),
            # The cap that matters is the room measured above the profile panel,
            # not a constant somebody once picked.
            Reading("the list is given more than 220 px", listed["cap"] > 220, True, note=f"{listed['cap']} px"),
            Reading("and does not have to scroll", listed["over"], 0, note=f"{listed['h']} px tall"),
            # The reported one: a wheel that started over a panel does not end in
            # a zoom, whether or not there was anything left to scroll.
            Reading("a wheel over the rows leaves the map alone", after, before),
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
    # **And plan mode goes off to pick the chain**, for the reason the undo
    # check names: while it is on, the panel stops answering clicks, so
    # selecting a chain selects nothing and this check skips itself. Which it
    # did under `--only`, where nothing before it had turned plan mode off --
    # a check that only runs in one order is a check that can stop running.
    page.evaluate("() => window.trailsPlan.toggle(false)")
    page.wait_for_timeout(500)
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
    settled(page)
    for at in places:
        page.evaluate("(where) => window.trailsPlan.place(where.lat, where.lon)", at)
        settled(page)
    settled(page)

    # **Named, because the name is what the file is for.** A reader asking what
    # their download is called is asking for the tour in it, and an unnamed tour
    # falls back to a stem that would never show whether the name travels.
    tour = "Vistenfjord runde"
    page.evaluate("() => window.trailsPlan.showList(true)")
    page.evaluate(SHOW_TOOL, "plan")
    page.wait_for_timeout(900)
    page.fill(".trails-plan-title", tour)
    # A real blur, because the field commits on one: one name is one change and
    # not one per keystroke.
    page.keyboard.press("Tab")
    settled(page)
    named = page.evaluate("() => window.trailsPlan.state().writable.stem")

    page.evaluate(SHOW_TOOL, "profile")
    page.wait_for_timeout(900)
    out = pathlib.Path(tempfile.mkdtemp(prefix="trails-drive-"))

    # **Named, not found by its words.** The button carries a mark now, like
    # every other tool on this page, so there is no text to match on -- and a
    # probe that aims by what a control *says* is a probe with an expiry date,
    # which this suite has already learned twice about aiming by position.
    press_download = """() => { document.querySelector('.trails-profile-gpx').click(); }"""
    with page.expect_download(timeout=25_000) as caught:
        page.evaluate(press_download)
    written = caught.value
    route = out / written.suggested_filename
    written.save_as(route)
    text = route.read_text(encoding="utf-8")

    # **The name has to leave the page, and the anchor is not the only way out
    # of it.** iOS Safari saves a `blob:` URL under the blob's own identifier
    # and ignores the anchor's name -- the cryptic file a reader reported, on a
    # route this page had already named correctly. Firefox offers no share sheet
    # to drive, so what is read here is this page's half of the bargain: given a
    # browser that offers one and a finger, the file goes through the sheet as a
    # `File` carrying the name and the whole body. The other half belongs to the
    # device and cannot be driven from here.
    page.evaluate(
        """() => { window.__shared = null;
        navigator.canShare = () => true;
        navigator.share = (data) => { window.__shared = data; return Promise.resolve(); }; }"""
    )
    page.evaluate("() => window.trailsChrome.coarse(true)")
    page.wait_for_timeout(500)
    page.evaluate(press_download)
    page.wait_for_timeout(500)
    handed = page.evaluate(
        """() => { const shared = window.__shared;
        if (!shared || !shared.files || !shared.files.length) { return null; }
        const file = shared.files[0];
        return {name: file.name, type: file.type, bytes: file.size, isFile: file instanceof File}; }"""
    )
    page.evaluate(
        """() => { window.trailsChrome.coarse(null);
        delete navigator.share; delete navigator.canShare; window.__shared = null; }"""
    )

    # **The same file, from the plan's own panel.** The button over the profile
    # is the one that has always written this, and on a narrow screen that panel
    # is not on the screen by default -- so the plan control offers it too, and
    # the two must be the same file and not two files that agree today.
    page.evaluate("() => window.trailsPlan.showList(true)")
    page.evaluate(SHOW_TOOL, "plan")
    page.wait_for_timeout(700)
    with page.expect_download(timeout=25_000) as caught:
        page.evaluate("() => document.querySelector('.trails-plan-gpx').click()")
    beside = out / ("beside-" + caught.value.suggested_filename)
    caught.value.save_as(beside)
    same = {"name": caught.value.suggested_filename, "bytes": beside.stat().st_size}

    # A stage, and the archive that gathers them.
    page.evaluate("() => window.trailsPlan.showList(true)")
    page.evaluate(SHOW_TOOL, "plan")
    page.wait_for_timeout(900)
    page.evaluate(
        """() => { const rows = [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage'));
        const cut = rows[1] && rows[1].querySelector('.trails-plan-cut');
        if (cut) { cut.click(); } }"""
    )
    settled(page)
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage')).length"""
    )
    # **Whether the cut took, said outright.** The archive is offered only where
    # there are stages to gather, so a cut that quietly did nothing reads as an
    # archive that was never offered -- which says nothing about why.
    marks = page.evaluate("() => window.trailsPlan.state().points.filter(point => typeof point.stage === 'string').length")
    offered = page.evaluate(
        """() => { const zip = document.querySelector('.trails-plan-zip');
        const box = zip ? zip.getBoundingClientRect() : null;
        return {there: !!zip, shown: !!(zip && zip.offsetParent !== null),
                boxes: zip ? zip.getClientRects().length : 0,
                wide: box ? Math.round(box.width) : 0, high: box ? Math.round(box.height) : 0,
                tool: window.trailsChrome.state().tool}; }"""
    )
    members: list[str] = []
    broken: str | None = "the archive was never offered"
    if offered["there"]:
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
    settled(page)
    offer = page.evaluate("() => window.trailsPlan.state().pending")
    restored = None
    if offer:
        page.evaluate("() => window.trailsPlan.take()")
        settled(page)
        restored = page.evaluate("() => window.trailsPlan.state().points.length")

    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(900)

    stages = [name for name in members if name != written.suggested_filename]
    return Check(
        "files written and read back",
        [
            Reading("a route downloads", written.suggested_filename.endswith(".gpx"), True, note=written.suggested_filename),
            Reading("the tour takes a name", named, tour),
            Reading("under the tour's own name", tour.replace(" ", "-") in written.suggested_filename, True),
            # What a phone does instead, because on a phone the anchor's name is
            # not carried and the sheet's is.
            Reading("a finger is handed the share sheet", bool(handed and handed["isFile"]), True, note=str(handed)),
            Reading("with the name on the file itself", handed["name"] if handed else None, written.suggested_filename),
            Reading("and the whole body with it", handed["bytes"] if handed else None, route.stat().st_size),
            Reading("and is a GPX", text.startswith('<?xml version="1.0" encoding="UTF-8"?>'), True),
            # One writer asked from two places, not two that agree today.
            Reading("the plan panel offers the same file", same["name"], written.suggested_filename),
            Reading("byte for byte", same["bytes"], route.stat().st_size),
            Reading("carrying its waypoints", text.count("<wpt ") > 0, True, note=f"{text.count('<wpt ')} wpt"),
            Reading("the list lists the points", rows, 4),
            Reading("a stage is cut", marks, 1),
            # **Whether the button is there, and not whether it is drawn.**
            # The guard here used to be `offsetParent !== null`, which is a lie
            # about a panel the chrome adopts into a holder: driven on its own,
            # the dock is shut, the button measures 0 x 0 and the archive was
            # silently never asked for -- the reading below then said the
            # archive did not open, which was never the question. Where the
            # panel is drawn is `chrome layout`'s reading, not this one's.
            Reading("the archive is offered", offered["there"] if offered else None, True, note=str(offered)),
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
    settled(page)
    empty = page.evaluate("() => window.trailsPlan.state().points.length")

    middle = page.evaluate(
        """() => { const r = document.querySelector('.leaflet-container').getBoundingClientRect();
        return {x: Math.round(r.left + r.width * 0.55), y: Math.round(r.top + r.height * 0.42)}; }"""
    )
    page.mouse.click(middle["x"], middle["y"])
    settled(page)
    clicked = page.evaluate("() => window.trailsPlan.state().points.length")

    # A pan ends in a click too, and how far the pointer travelled is what tells
    # the two apart -- measured from where the gesture began, which is what
    # pointerdown records.
    page.mouse.move(middle["x"] - 120, middle["y"] + 60)
    page.mouse.down()
    page.mouse.move(middle["x"] - 40, middle["y"] + 20, steps=8)
    page.mouse.up()
    settled(page)
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
      // **Computed and not the inline value.** These carry `var(--trails-...)`
      // now, and `style.color` gives back the declaration rather than a colour.
      return b ? {title: b.title, disabled: b.disabled,
                  colour: getComputedStyle(b).color} : null; }"""
    shown = """() => { const open = [...document.querySelectorAll('.trails-chrome-body > div')]
        .filter(node => node.offsetParent !== null);
      const empty = document.querySelector('.trails-profile-empty');
      return {holders: open.length, empty: !!(empty && empty.offsetParent !== null),
              says: open.length === 1 ? open[0].textContent.trim().slice(0, 60) : ''}; }"""

    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(500)
    at_rest = page.evaluate(button)

    page.evaluate(SHOW_TOOL, "profile")
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
    page.evaluate(SHOW_TOOL, "profile")
    page.wait_for_timeout(600)
    folded_px = page.evaluate(tall)
    page.evaluate(SHOW_TOOL, "profile")
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
    rects = "() => document.querySelectorAll('.trails-profile-chart rect').length"
    reset = """() => { const chart = document.querySelector('.trails-profile-chart');
        chart.dispatchEvent(new MouseEvent('dblclick', {bubbles: true, cancelable: true})); }"""

    page.evaluate(reset)
    page.wait_for_timeout(600)
    whole = page.evaluate(view)
    at_rest = page.evaluate(rects)

    box = page.evaluate(
        """() => { const r = document.querySelector('.trails-profile-chart').getBoundingClientRect();
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
    settled(page)
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
        settled(page)
    settled(page)
    laid = page.evaluate(ids)

    def take_back() -> Any:
        page.evaluate("() => window.trailsPlan.undo()")
        settled(page)
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
    settled(page)
    inserted = page.evaluate(ids)
    after_insert = take_back()

    # 2. a removal, which a pop could never take back: it has to put one in.
    page.evaluate("() => window.trailsPlan.remove(1)")
    settled(page)
    shorter = page.evaluate(ids)
    after_remove = take_back()

    # 3. a reorder, which changes no count at all.
    page.evaluate("() => window.trailsPlan.moveTo(3, 1)")
    settled(page)
    reordered = page.evaluate(ids)
    after_move = take_back()

    # 4. a stage mark, which changes no points.
    page.evaluate("() => window.trailsPlan.showList(true)")
    page.evaluate(SHOW_TOOL, "plan")
    page.wait_for_timeout(900)
    pressed = page.evaluate(
        """() => { const rows = [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage'));
        const cut = rows[1] && rows[1].querySelector('.trails-plan-cut');
        if (!cut) { return 'no cut button on row 2 of ' + rows.length; }
        cut.click(); return 'pressed'; }"""
    )
    settled(page)
    stages = page.evaluate("() => window.trailsPlan.state().points.filter(p => typeof p.stage === 'string').length")

    # **Measured here because this is where all three exist at once.** A
    # stage heading has a name field only while a stage does, and iOS Safari
    # zooms the whole page when a field under 16 px takes focus -- which on a
    # map is the reader losing their place in order to type a name. The
    # search got that rule when it was written and these two did not.
    fields = """() => { const of = sel => { const node = document.querySelector(sel);
        if (!node || node.offsetParent === null) { return null; }
        const seen = node.getBoundingClientRect();
        return [Math.round(seen.height), Math.round(parseFloat(getComputedStyle(node).fontSize))]; };
      return {tour: of('.trails-plan-title'), stage: of('.trails-plan-stage-name')}; }"""
    page.evaluate("() => window.trailsChrome.coarse(true)")
    page.wait_for_timeout(500)
    finger = page.evaluate(fields)
    page.evaluate("() => window.trailsChrome.coarse(null)")
    page.wait_for_timeout(500)
    mouse = page.evaluate(fields)
    take_back()
    page.wait_for_timeout(600)
    stages_back = page.evaluate("() => window.trailsPlan.state().points.filter(p => typeof p.stage === 'string').length")

    # And it stops rather than eating the route when there is nothing left.
    drained = page.evaluate(
        """() => { for (let i = 0; i < 60; i += 1) { window.trailsPlan.undo(); }
        return window.trailsPlan.state().undoable; }"""
    )
    settled(page)
    emptied = page.evaluate("() => window.trailsPlan.state().points.length")
    page.evaluate("() => { for (let i = 0; i < 5; i += 1) { window.trailsPlan.undo(); } }")
    settled(page)
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
            Reading("with a finger the tour's name is 40 px of 16 px type", finger["tour"], [40, 16]),
            Reading("and a stage's name too", finger["stage"], [40, 16]),
            Reading("with a mouse they are what they were", [mouse["tour"], mouse["stage"]], [[21, 12], [21, 12]]),
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


def reading_with_a_finger(page: Any) -> Check:
    """What is under a touch, which is the one thing this panel is for.

    Reported by a reader: on a phone there is no way to pick a place on the curve
    and be told its height, its gradient and where it is. There was not — the
    reading, the blue rule and the mark on the map all hung off ``mousemove``,
    and a finger never fires one. **The panel's whole purpose was mouse-only.**

    One finger reads now and two move and zoom, which is where a map puts them;
    a finger used to move the window, which meant a reader with one could never
    get the reading at all — and on the 99 % of chains with nothing to zoom into
    it did not even do that.

    **The events here are dispatched and the delivery is proved elsewhere.** A
    synthetic touch drives the handler and says nothing about whether a browser
    starts one, which is the caveat this suite already carries about dragging.
    Driven separately with ``page.touchscreen.tap`` in a real touch context, a
    tap at 45 % of the 42 km chain reads *16.02 km · 652 m · +2 %* and one at
    75 % reads *31.62 km · 597 m · −17 %, steep*.

    Args:
        page: The driven page, with a chain selected

    Returns:
        What a touch put on the panel and on the map

    """
    touch = """(where) => { const chart = document.querySelector('.trails-profile-chart');
      const box = chart.getBoundingClientRect();
      const at = {clientX: box.left + box.width * where, clientY: box.top + box.height / 2};
      const fire = kind => { const event = new Event(kind, {bubbles: true, cancelable: true});
        event.touches = kind === 'touchend' ? [] : [at];
        event.changedTouches = [at];
        chart.dispatchEvent(event); };
      fire('touchstart'); fire('touchmove'); fire('touchend'); }"""
    seen = """() => { const chart = document.querySelector('.trails-profile-chart');
      const shown = [...chart.querySelectorAll('text')].filter(n => n.style.display !== 'none')
        .map(n => n.textContent);
      // **Against the token and not a hex this check remembers.** The
      // crosshair's blue is the page's accent now — one blue, in the rail and on
      // the curve — and a check holding the old literal reads zero rules and
      // says the crosshair is gone.
      const accent = getComputedStyle(document.documentElement)
        .getPropertyValue('--trails-accent').trim();
      const rules = [...chart.querySelectorAll('line')]
        .filter(n => n.getAttribute('stroke') === accent && n.style.display !== 'none').length;
      const pane = document.querySelector('.leaflet-trailsProfileHere-pane');
      const mark = pane ? [...pane.children].filter(n => n.style.display !== 'none').length : 0;
      // **The reading is in the heading now, and the heading's colour says
      // so.** It used to be a `<text>` at `box.right` on the same line a hint was
      // written to from `box.left`, and on 390 px the two lay over each other.
      // There is no second place for it to be drawn any more, which is what
      // makes that collision impossible rather than merely fixed.
      const head = document.querySelector('.trails-profile-figures');
      const said = head ? head.textContent : '';
      const reading = (head && head.classList.contains('trails-profile-reading')) ? said : null;
      return {reading: reading, rules: rules, mark: mark, said: said,
              // Nothing in the plot may tell a reader what to do: both hints are
              // gone, on every pointer, and nothing stands in for them.
              told: shown.find(s => /read it|stretch|Touch|drag|pinch/i.test(s)) || null}; }"""

    page.evaluate("() => window.trailsChrome.coarse(true)")
    page.wait_for_timeout(500)
    before = page.evaluate(seen)
    page.evaluate(touch, 0.45)
    page.wait_for_timeout(700)
    near = page.evaluate(seen)
    page.evaluate(touch, 0.75)
    page.wait_for_timeout(700)
    far = page.evaluate(seen)
    page.evaluate("() => window.trailsChrome.coarse(null)")
    page.wait_for_timeout(500)
    on_a_mouse = page.evaluate(seen)

    return Check(
        "reading the curve with a finger",
        [
            Reading("nothing is read until something is touched", before["reading"], None),
            Reading("a touch reads a place", bool(near["reading"]), True, note=near["reading"]),
            Reading("with the blue rule on it", near["rules"], 1),
            # The mark on the map is the other half of the answer: a reader
            # following a climb wants to see where it is.
            Reading("and the mark on the map", near["mark"], 1),
            Reading("touching elsewhere reads elsewhere", far["reading"] != near["reading"], True, note=far["reading"]),
            # **And nothing in the plot tells a reader what to do.** Both hint
            # lines are gone, on both pointers, and nothing replaces them here or
            # in the sheet. What a reader sees instead is state: the *whole
            # chain* button, which stands exactly while there is something to go
            # back from.
            Reading("no instruction is drawn on a finger", far["told"], None),
            Reading("and none on a mouse", on_a_mouse["told"], None),
        ],
    )


# ---------------------------------------------------------------------------


def where_the_reader_is(page: Any) -> Check:
    """A dot for the reader's own position, and the accuracy drawn with it.

    **The accuracy is the point.** A fix is a claim with a radius on it -- 8 m
    under an open sky, 300 m in a valley -- and a page that draws it as a dot has
    thrown away the half that matters on a mountain. On a map whose whole
    argument is metres per pixel, the circle is the only honest way to show one.

    Playwright answers the browser's question for the reader it does not have, so
    both halves are driveable: that nothing is watched until it is asked for, and
    that what arrives is drawn where it says.

    Args:
        page: The driven page, at any state

    Returns:
        What is drawn before and after, and what the map did about it
    """
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(500)
    page.evaluate("() => window.trailsChrome.close()")
    # **It lays its own view down**, like the file check lays its own route. The
    # checks before this leave the map wherever they were looking, and both
    # questions here — did it move to the fix, and is the circle the reported
    # accuracy at this scale — are answered against a scale.
    page.evaluate(f"() => {MAP_OBJECT}.setView([65.60, 13.20], 11)")
    page.wait_for_timeout(700)
    page.evaluate(SHOW_TOOL, "here")
    page.wait_for_timeout(600)

    seen = """() => {
      const map = window[Object.keys(window).find(k => k.startsWith('map_'))];
      // **Drawn into the canvas, so there is no element to ask.** The dot and
      // the ring are layers on the map and are found as layers; a reader who
      // has stopped the watch has neither, which is what this used to learn
      // from `querySelector` answering null.
      let dot = null, ring = null;
      map.eachLayer(l => { const cls = l.options && l.options.className;
        if (cls === 'trails-here-dot') { dot = l; }
        if (cls === 'trails-here-ring') { ring = l; } });
      // **A circle has no `r` to read either way**: the question is how wide it
      // comes out on the screen, which is the question anyway — the circle has
      // to be the reported accuracy at this map's scale. Its own bounds,
      // projected, answer that under either renderer.
      let across = 0;
      if (ring) { const box = ring.getBounds();
        across = Math.round(map.latLngToContainerPoint(box.getSouthEast()).x
                            - map.latLngToContainerPoint(box.getNorthWest()).x); }
      const metres = map.distance(map.containerPointToLatLng([0, 0]),
                                  map.containerPointToLatLng([100, 0])) / 100;
      return {dot: !!dot, ring: !!ring, across: across,
              wanted: Math.round(2 * 24 / metres),
              said: (document.querySelector('.trails-here-state') || {}).textContent || '',
              button: (document.querySelector('.trails-here-toggle') || {}).textContent || '',
              centre: map.getCenter(), zoom: map.getZoom()}; }"""

    before = page.evaluate(seen)
    page.evaluate("() => document.querySelector('.trails-here-toggle').click()")
    page.wait_for_function(
        with_map(
            """() => { let seen = false;
            __MAP__.eachLayer(l => { if (l.options && l.options.className === 'trails-here-dot') { seen = true; } });
            return seen; }"""
        ),
        timeout=20_000,
    )
    page.wait_for_timeout(600)
    after = page.evaluate(seen)
    # **Read with the dock shut.** An open tool's button is lit white on the
    # accent; what is being asked here is the other thing the rail says — that
    # something is *running* behind a closed panel.
    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(500)
    lit = page.evaluate(
        """() => { const b = document.querySelector('.trails-rail button[data-tool=here]');
        return b ? getComputedStyle(b).color : ''; }"""
    )
    page.evaluate(SHOW_TOOL, "here")
    page.wait_for_timeout(500)

    page.evaluate("() => document.querySelector('.trails-here-toggle').click()")
    page.wait_for_timeout(600)
    stopped = page.evaluate(seen)

    # **And a reader standing somewhere this map has never drawn.** Oslo is 500
    # km from the park: a dot there would be a dot on a blank square, which is
    # not an answer. It says where they are and stops watching, because there is
    # no point following a position it cannot draw.
    page.context.set_geolocation({"latitude": 59.913, "longitude": 10.752, "accuracy": 20})
    page.evaluate(SHOW_TOOL, "here")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('.trails-here-toggle').click()")
    page.wait_for_timeout(2500)
    elsewhere = page.evaluate(seen)
    page.context.set_geolocation({"latitude": 65.55, "longitude": 13.05, "accuracy": 24})

    page.evaluate("() => window.trailsChrome.close()")
    page.wait_for_timeout(400)

    moved = round(((after["centre"]["lat"] - 65.55) ** 2 + (after["centre"]["lng"] - 13.05) ** 2) ** 0.5, 4)
    return Check(
        "where the reader is",
        [
            # Nothing is watched because the tool was opened: a map that starts
            # following a reader on its own has decided something for them.
            Reading("nothing is drawn until it is asked for", before["dot"], False),
            Reading("and the button offers it", before["button"], "Show my position"),
            Reading("a fix draws a dot", after["dot"], True),
            # The half that matters: the radius the browser reported, at the
            # map's own scale.
            Reading("with the accuracy around it", after["ring"], True),
            Reading(
                "drawn at the reported metres",
                after["across"],
                after["wanted"],
                within=3,
                note=f"{after['across']} px across, {after['wanted']} wanted for 24 m",
            ),
            Reading("and said in words too", "24 m" in after["said"], True, note=after["said"][:70]),
            # Moved once, to a fix that is near what is on the screen.
            Reading("the map went to it", moved < 0.05, True, note=str(moved)),
            Reading("the rail says it is watching", lit, "rgb(13, 71, 161)"),
            # And pressing again stops: the watch, the dot and the circle.
            Reading("pressing again stops the watch", stopped["dot"] or stopped["ring"], False),
            Reading("and offers it again", stopped["button"], "Show my position"),
            # Outside the drawn ground: said, not drawn, and not followed.
            Reading("a position off the map draws nothing", elsewhere["dot"] or elsewhere["ring"], False),
            Reading("and says so", "outside the ground this map draws" in elsewhere["said"], True, note=elsewhere["said"][:80]),
            Reading("with how far off it is", "km from it" in elsewhere["said"], True),
            Reading("and stops watching", elsewhere["button"], "Show my position"),
        ],
    )


def the_dark_set(page: Any) -> Check:
    """Two sets of colours for the furniture, and one for the ground.

    **The tiles cannot turn and must not.** A Kartverket sheet arrives as a
    finished raster; an inverted slope is not a dark slope, it is a wrong one.
    So this asks two separate questions: whether the panels followed the
    machine, and whether the drawing stayed where the data put it.

    Driven with ``emulate_media``, which is the actual media query and not a
    class this page sets for itself -- the one thing about the theme a browser
    is needed for.

    Args:
        page: The driven page, with a chain selected

    Returns:
        What the panels measure in each set, the contrast in each, and what did
        not move between them
    """
    read = """() => {
      const paint = sel => { const node = document.querySelector(sel);
        if (!node) { return null; }
        const seen = getComputedStyle(node);
        return {bg: seen.backgroundColor, fg: seen.color}; };
      const band = document.querySelector('.trails-profile-chart polyline, .trails-profile-chart path');
      const tile = document.querySelector('.leaflet-tile');
      return {panel: paint('.trails-profile-panel'), rail: paint('.trails-rail'),
              zoom: paint('.leaflet-control-zoom a'),
              band: band ? getComputedStyle(band).stroke : null,
              tiles: tile ? getComputedStyle(tile).filter : null}; }"""

    def channels(colour: str) -> tuple[float, float, float]:
        """Pull the three channels out of an rgb() or rgba() string."""
        numbers = [float(part) for part in re.findall(r"[\d.]+", colour or "")][:3]
        return tuple(numbers) if len(numbers) == 3 else (0.0, 0.0, 0.0)  # type: ignore[return-value]

    def contrast(front: str, back: str) -> float:
        """WCAG contrast between two rgb strings, 1 to 21."""

        def light(colour: str) -> float:
            parts = []
            for raw in channels(colour):
                unit = raw / 255
                parts.append(unit / 12.92 if unit <= 0.03928 else ((unit + 0.055) / 1.055) ** 2.4)
            return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

        first, second = light(front), light(back)
        high, low = max(first, second), min(first, second)
        return (high + 0.05) / (low + 0.05)

    page.emulate_media(color_scheme="light")
    page.wait_for_timeout(500)
    light = page.evaluate(read)
    page.emulate_media(color_scheme="dark")
    page.wait_for_timeout(700)
    dark = page.evaluate(read)
    page.emulate_media(color_scheme="light")
    page.wait_for_timeout(400)

    def darker(part: str) -> bool:
        return sum(channels(dark[part]["bg"])) < sum(channels(light[part]["bg"])) - 90

    return Check(
        "the furniture turns and the ground does not",
        [
            Reading("the profile panel turns", darker("panel"), True, note=f"{light['panel']['bg']} to {dark['panel']['bg']}"),
            Reading("the tool rail turns", darker("rail"), True),
            # Leaflet's own buttons come painted from its stylesheet, so they
            # need the page to say otherwise or they stay white on a dark map.
            Reading("and so do the zoom buttons", darker("zoom"), True, note=f"{light['zoom']['bg']} to {dark['zoom']['bg']}"),
            # A panel nobody can read is not a dark theme. 4.5 is the ordinary
            # text threshold; these are 12 px labels, so it is the right one.
            Reading(
                "readable in the light set",
                round(contrast(light["panel"]["fg"], light["panel"]["bg"]), 1),
                15.1,
                within=3.0,
                holds=False,
            ),
            Reading(
                "and readable in the dark one",
                contrast(dark["panel"]["fg"], dark["panel"]["bg"]) >= 4.5,
                True,
                note=f"{contrast(dark['panel']['fg'], dark['panel']['bg']):.1f}:1",
            ),
            # **The drawing is not furniture.** Green meaning gentle in the
            # morning and something else at night would be the curve lying to
            # keep up with the panels.
            Reading("the gradient bands do not turn", dark["band"], light["band"]),
            # And the terrain least of all: no filter, in either set.
            Reading("nor is anything done to the tiles", dark["tiles"], light["tiles"], note=str(light["tiles"])),
        ],
    )


def a_plan_survives_a_reload(page: Any) -> Check:
    """Reloading the page, and finding the plan still there.

    **The only check here that reloads**, and the only one that can answer this
    at all: what is being measured is what a browser does between two page
    loads, and every other reading in this file is taken inside one. It costs
    the page load again -- about 25 seconds -- which is why it runs last and why
    it is one check and not four.

    What has to come back is not just the points. A plan is its waypoints, the
    marks that cut it into stages, the tour's name, and whether the reader was
    still planning when they left; the route between the points is routed again
    rather than restored, which is deliberate and is what brings the ground back
    with it.

    Args:
        page: The driven page, at any state

    Returns:
        The plan before the reload, the plan after it, and what keeping cost
    """
    page.set_viewport_size({"width": 1400, "height": 900})
    page.wait_for_timeout(600)
    page.evaluate("() => { window.trailsChrome.close(); window.trailsPlan.toggle(false); }")
    page.wait_for_timeout(500)
    if not select(page, LONG_CHAIN):
        return Check("a plan survives a reload", skipped=f"{LONG_CHAIN} is not in this page")
    places = page.evaluate(
        """() => { const shape = window.trailsProfile.shape;
        return [0.1, 0.4, 0.7].map(f => Math.floor(f * (shape.lon.length - 1)))
          .map(i => ({lat: shape.lat[i], lon: shape.lon[i]})); }"""
    )
    page.evaluate("() => window.trailsPlan.toggle(true)")
    page.wait_for_timeout(600)
    page.evaluate(
        """() => { const standing = window.trailsPlan.state().points.length;
        for (let i = 0; i < standing; i += 1) { window.trailsPlan.remove(0); } }"""
    )
    settled(page)
    for at in places:
        page.evaluate("(where) => window.trailsPlan.place(where.lat, where.lon)", at)
        settled(page)
    settled(page)

    # A name and a cut, both through the controls a reader uses. `.click()` and
    # `focus()`/`blur()` rather than a real press: this check is about what
    # survives a reload, and where those controls are drawn is `chrome layout`'s
    # reading.
    tour = "Strompdalen over"
    page.evaluate("() => window.trailsPlan.showList(true)")
    page.evaluate(SHOW_TOOL, "plan")
    page.wait_for_timeout(800)
    page.evaluate(
        """(name) => { const title = document.querySelector('.trails-plan-title');
        title.focus(); title.value = name; title.blur(); }""",
        tour,
    )
    settled(page)
    page.evaluate(
        """() => { const rows = [...document.querySelectorAll('.trails-plan-points > div')]
          .filter(row => !row.classList.contains('trails-plan-stage'));
        const cut = rows[1] && rows[1].querySelector('.trails-plan-cut');
        if (cut) { cut.click(); } }"""
    )
    settled(page)

    reading = """() => { const state = window.trailsPlan.state();
        return {points: state.points.length, stem: state.writable.stem,
                walked: Math.round(state.walked), on: state.on,
                cuts: state.points.filter(point => typeof point.stage === 'string').length}; }"""
    before = page.evaluate(reading)
    # Written on the spot rather than waited for: the debounce is 1.2 s after
    # the last edit, and a check that slept for it would be measuring the sleep.
    page.evaluate("() => window.trailsPlan.keep()")
    kept = page.evaluate("() => window.trailsPlan.kept()")

    began = time.monotonic()
    page.reload(timeout=120_000)
    page.wait_for_timeout(SETTLE_MS)
    restored = True
    try:
        page.wait_for_function(
            "() => window.trailsPlan && window.trailsPlan.state().points.length > 0",
            timeout=60_000,
        )
    except Exception:
        restored = False
    if restored:
        settled(page)
    took = round(time.monotonic() - began, 1)
    after = page.evaluate(reading) if restored else {}
    said = page.evaluate("() => window.trailsPlan.state().loaded") if restored else None

    # **And the way out of it.** A plan restored on every load has to have one,
    # or a reader who wants a clean map has to empty a twenty-point route a
    # point at a time. It goes through the same edit funnel as everything else,
    # so undo brings it back -- which is what makes clearing the map safe.
    page.evaluate(
        """() => { if (window.trailsChrome.state().tool !== 'plan') { window.trailsChrome.open('plan'); }
        document.querySelector('.trails-plan-fresh').click(); }"""
    )
    settled(page)
    page.evaluate("() => window.trailsPlan.keep()")
    cleared = page.evaluate("() => ({points: window.trailsPlan.state().points.length, kept: window.trailsPlan.kept()})")
    page.evaluate("() => window.trailsPlan.undo()")
    settled(page)
    again = page.evaluate("() => window.trailsPlan.state().points.length")

    return Check(
        "a plan survives a reload",
        [
            Reading("a plan is kept at all", bool(kept), True, note=str(kept and kept["key"])),
            # The price of one writer and one reader: the kept copy is the file
            # the download button offers, `<trkpt>` and all, and those are
            # routed again on the way back in rather than read.
            Reading("what it weighs", round((kept["bytes"] if kept else 0) / 1024), 549, within=250, holds=False, note="kB"),
            Reading("and what writing it cost", kept["ms"] if kept else None, 34, within=40, holds=False, note="ms"),
            Reading("the points come back", after.get("points"), before["points"]),
            Reading("the stage marks come back", after.get("cuts"), before["cuts"]),
            Reading("the tour's name comes back", after.get("stem"), before["stem"]),
            # Routed again, not copied -- so this is the same ground and not a
            # remembered number.
            Reading("and the same ground under them", after.get("walked"), before["walked"], within=1),
            # A reader who was planning is still planning; one who had finished
            # does not find every tap placing a point.
            Reading("still planning, as they were", after.get("on"), before["on"]),
            Reading("what the reader is told", "Back as you left it" in ((said or {}).get("said") or ""), True, note=(said or {}).get("said") or ""),
            Reading("and how long it took to come back", took, 21, within=20, holds=False, note="s, load included"),
            Reading("starting again clears the map", cleared["points"], 0),
            Reading("and forgets what was kept", cleared["kept"], None),
            Reading("and undo brings it back", again, before["points"]),
        ],
    )


class _Quiet(http.server.SimpleHTTPRequestHandler):
    """A file server that does not narrate, and counts what it is asked for.

    The count is the point. A worker that caches the map by fetching it again
    would make the first visit pay for it twice -- 6.58 MB against 13 on a
    connection where that is forty seconds against eighty -- and nothing on the
    page would look wrong. The browser's own cache is what makes it free, and
    *free* is a thing to measure rather than to reason about.
    """

    #: How often each path was asked for with a GET, across every instance.
    asked: dict[str, int] = {}

    #: And with a HEAD, counted apart. `send_head` runs for both, so counting
    #: them together would put the worker's cheap "has it moved?" into the figure
    #: that says how many times the 5.2 MB map was actually downloaded.
    heads: dict[str, int] = {}

    def log_message(self, format: str, *args: Any) -> None:
        """Say nothing.

        Args:
            format: Ignored.
            *args: Ignored.
        """

    def send_head(self) -> Any:
        """Count the request, then answer it as usual.

        Returns:
            Whatever the handler this one is built on answers.
        """
        counted = _Quiet.heads if self.command == "HEAD" else _Quiet.asked
        counted[self.path] = counted.get(self.path, 0) + 1
        return super().send_head()


@contextlib.contextmanager
def served(directory: pathlib.Path) -> Any:
    """Serve a directory over HTTP for as long as the block runs.

    **A service worker needs an origin**, and every other check in this suite
    reads the page off the disk. `file://` is not a secure context, so a worker
    cannot be registered there at all -- which would have left the one thing this
    project says about itself, that anything visible is driven before it is
    believed, unkept for the one feature whose whole job is to work when nothing
    else does.

    Args:
        directory: What to serve, which is where the build writes.

    Yields:
        The origin it is reachable at.
    """
    _Quiet.asked = {}
    handler = functools.partial(_Quiet, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


#: Whether the page this is running in is in the worker's own cache, asked of
#: the cache rather than of the worker: what matters is that the bytes are there
#: under the address the reader used, not that a registration succeeded.
CACHED_PAGE = """async () => {
    for (const name of await caches.keys()) {
        if (!name.startsWith('trails-page-')) { continue; }
        const cache = await caches.open(name);
        if (await cache.match(location.href)) { return true; }
    }
    return false; }"""


def the_zoom_the_scale_says(page: Any) -> Check:
    """The map saying which zoom it is drawing at.

    **Because the offline chooser asks the reader for one.** A reader picking
    *z16* out of a list has no way to see what z16 looks like unless the map says
    what it is showing, and a number nobody ever meets again is a number nobody
    can choose between.

    The pairing is arithmetic and not a lookup: ``L.control.scale`` uses
    ``maxWidth: 100``, and at 65.5 N the ground resolution is 64,917 / 2^z. So
    the bar reads 100 m at z15, 50 m at z16 and 30 m at z17, and no reading is
    shared by two zooms -- which is what makes a screenshot readable back to a
    zoom, something every report about this page has so far had to guess at.

    Args:
        page: A page already loaded and settled

    Returns:
        What the line said, at two zooms and against the bar beside it.

    """
    was = page.evaluate(with_map("() => ({at: __MAP__.getCenter(), z: __MAP__.getZoom()})"))
    readings = []
    for zoom, bar in ((15, "100 m"), (16, "50 m")):
        page.evaluate(with_map(f"() => __MAP__.setView([65.55, 13.05], {zoom})"))
        page.wait_for_timeout(400)
        said = page.evaluate(
            """() => ({
                zoom: (document.querySelector('.trails-scale-zoom') || {}).textContent,
                bar: (document.querySelector('.leaflet-control-scale-line') || {}).textContent
            })"""
        )
        readings.append(Reading(f"at z{zoom} the line says so", (said["zoom"] or "").split(" ")[0], f"z{zoom}"))
        readings.append(Reading(f"and the bar beside it reads {bar}", said["bar"], bar))
    # A metres-per-pixel figure, because that is what this whole map argues in.
    said = page.evaluate("() => (document.querySelector('.trails-scale-zoom') || {}).textContent")
    readings.append(Reading("and it says the ground it is drawing at", "m/px" in (said or ""), True, note=said or ""))
    page.evaluate(with_map(f"() => __MAP__.setView([{was['at']['lat']}, {was['at']['lng']}], {was['z']})"))
    page.wait_for_timeout(300)
    return Check("the scale bar says which zoom it is", readings)


#: The piece of ground the offline check keeps, and the shape of it matters.
#:
#: **The chooser's viewport scope is gone**, so the small real download below is
#: an area the reader drew, set through ``area()`` -- which is the seam that
#: exists for exactly this. About 5 x 9 km round 65.55 N 13.05 E: 176 tiles at
#: z14 and 416 at z15, which is a check and not a bulk fetch off somebody else's
#: service, and wide enough to cover the 1400 x 900 viewport the offline visit
#: looks at, so that *the kept ground draws* is asking about coverage rather than
#: about luck.
KEPT_AREA = [[65.528, 12.955], [65.572, 12.955], [65.572, 13.145], [65.528, 13.145]]

#: Set that area and take the coarsest zoom the chooser offers.
KEEP_AREA = """async (ring) => {
    await window.trailsOffline.area(ring);
    return await window.trailsOffline.choose('draw', 14);
}"""

#: What the preview has actually coloured in, in tiles' worth of paint.
#:
#: **Counted in pixels and not in tiles**, because the whole question is whether
#: a screen tile was filled in whole where only a corner of it was kept. A tile
#: left over from the zoom that just happened is still in the pane, drawn scaled;
#: its bounding rectangle says so, and it is not counted, because it belongs to a
#: level nobody is looking at any more.
PAINTED = """() => {
    const pane = document.querySelector('.leaflet-trailsOffline-pane');
    if (!pane) { return null; }
    let filled = 0, seen = 0;
    pane.querySelectorAll('canvas').forEach(canvas => {
        const box = canvas.getBoundingClientRect();
        if (Math.abs(box.width - 256) > 2) { return; }
        seen += 1;
        const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
        let lit = 0;
        for (let i = 3; i < data.length; i += 4) { if (data[i]) { lit += 1; } }
        filled += lit / (canvas.width * canvas.height);
    });
    return {tiles: seen, filled: filled};
}"""

#: What the panel says it is colouring in, which the reading above is held
#: against. The line exists because the same selection is a different number of
#: tiles on every level, and without it the shape looks as though it grew when
#: the reader zoomed out.
SAID_LAYER = "() => (document.querySelector('.trails-offline-layer') || {}).textContent || ''"

#: Which pieces of ground the chooser is offering. Two of the four need a line
#: to be drawn round and are not offered when there is none.
SCOPES_OFFERED = "() => Array.from(document.querySelectorAll('.trails-offline-scope')).map(b => b.getAttribute('data-scope'))"

#: What the chooser says the selection is, which includes the line it took.
SAID_NEEDED = "() => (document.querySelector('.trails-offline-needed') || {}).textContent || ''"

#: What the panel says while a run is going: `Keeping <done> of <total>`. The
#: figure that matters is the one it opens with — a run resumed after a lock or a
#: tunnel counts what is already kept as done, and used to start at zero and race
#: up through tiles it was skipping, which reads as starting the download again.
SAID_FIGURES = "() => (document.querySelector('.trails-offline-figures') || {}).textContent || ''"


def painted_ground(page: Any) -> tuple[float, float, str]:
    """How much ground the preview has coloured in, and how much it says it has.

    Args:
        page: The page, with the chooser open and a selection made.

    Returns:
        The area painted on the screen in km2, the area the panel says the level
        it is drawing covers in km2, and the sentence it said it in.
    """
    painted = page.evaluate(PAINTED) or {"filled": 0.0}
    where = page.evaluate(with_map("() => ({z: __MAP__.getZoom(), lat: __MAP__.getCenter().lat})"))
    side = 40075016.686 * math.cos(math.radians(where["lat"])) / 2 ** where["z"] / 1000
    said = page.evaluate(SAID_LAYER)
    quoted = re.search(r"about ([\d,]+) km2", said)
    return painted["filled"] * side * side, float(quoted.group(1).replace(",", "")) if quoted else 0.0, said


#: Wait for the chooser's count and read it in the same breath.
#:
#: **Two calls is a race, and it became a reachable one.** The panel nulls the
#: figure whenever the selection moves and works it out again off the paint, so
#: `wait_for_function` and then `evaluate` can land either side of that. It was
#: survivable while a refresh took a couple of hundred milliseconds enumerating
#: the terrain cache; a refresh is now four, and the harness lost every time.
COUNTED = """(was) => {
    const said = window.trailsOffline.state();
    if (!said || !said.counted) { return null; }
    if (was !== null && said.counted.at === was) { return null; }
    return {tiles: said.counted.tiles, at: said.counted.at};
}"""


def counted_now(page: Any, after: str | None = None, timeout: int = 60_000) -> dict:
    """The figure the chooser has settled on, and which selection it belongs to.

    **`after` is what makes this a measurement rather than a coincidence.** The
    figure carries `at`, the selection's own signature, so waiting for one that
    is *not* the signature already in hand is the difference between reading the
    count after a drag and reading the one that was on the screen before it.
    Without that, a check reads whatever is there and passes when nothing moved.

    Args:
        page: The driven page, with the chooser open
        after: A signature to wait past, or None for whatever is there
        timeout: How long to wait for a figure

    Returns:
        ``{"tiles": int, "at": str}`` for the settled selection.
    """
    settled = page.wait_for_function(COUNTED, arg=after, timeout=timeout).json_value()
    return {"tiles": int(settled["tiles"]), "at": str(settled["at"])}


def what_the_chooser_draws(page: Any) -> list[Reading]:
    """The chooser's own drawing, driven, because none of it is in the source.

    **Three things the panel claims that only a browser can settle.** A source
    test can read the arithmetic and see that the preview paints sub-rectangles;
    it cannot see that the result is the right piece of ground. It can see that a
    handle is draggable; it cannot see that dragging one moves the selection. It
    can see that a button is given ``disabled``; it cannot see it refuse a press.

    The first is the one this exists for. Colouring the whole screen tile
    whenever it holds any kept tile looks right at the zoom the area was drawn
    at and turns a valley into a county three zooms out -- which is how it was
    reported, from a phone, and it is invisible in the source either way.

    Args:
        page: The page, online, with the chooser open on a drawn area.

    Returns:
        What each of the three measured.
    """
    out: list[Reading] = []

    # **Which line the band and the box are drawn round.** With neither a planned
    # route nor a selected track the two scopes are not offered at all, and this
    # page opens with neither -- so selecting a chain has to bring them back, and
    # the panel has to say which of the two it took. `shape` is decoded out of
    # the routing graph a microtask after the click and the panel reads it there;
    # nothing in the source can show that it arrives.
    without = page.evaluate(SCOPES_OFFERED)
    out.append(Reading("with no line to follow, only the two scopes that need none", without, ["all", "draw"]))
    if select(page, LONG_CHAIN):
        page.evaluate("async () => await window.trailsOffline.choose('band', 15)")
        page.wait_for_function(
            "() => { const s = window.trailsOffline.state(); return s && s.counted && s.counted.scope === 'band'; }",
            timeout=60_000,
        )
        said_line = page.evaluate(SAID_NEEDED)
        out.append(Reading("selecting a track brings the other two back", page.evaluate(SCOPES_OFFERED), ["all", "band", "rect", "draw"]))
        out.append(Reading("and the panel says which line it took", "the track you have selected" in said_line, True, note=said_line[:110]))
        # **Toggled off again**, or every figure below is read with a chain
        # highlighted and the offline page's, loaded fresh, is not.
        page.evaluate(SELECT_CHAIN, LONG_CHAIN)
    else:
        out.append(Reading("selecting a track brings the other two back", "no such chain", LONG_CHAIN))
    page.evaluate(KEEP_AREA, KEPT_AREA)
    page.wait_for_function("() => { const s = window.trailsOffline.state(); return s && s.counted; }", timeout=60_000)

    # Close in, where the selection is bigger than the window: the paint is the
    # window, and the panel says the level covers more ground than is on screen.
    page.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 14)"))
    page.wait_for_timeout(1500)
    close, said_close, sentence = painted_ground(page)
    out.append(Reading("the panel says which level it is colouring in", "level z" in sentence, True, note=sentence[:96]))
    out.append(
        Reading(
            "and close in, the paint is inside what it says",
            close <= said_close * 1.5,
            True,
            note=f"{close:.0f} km2 painted, {said_close:.0f} km2 said",
        )
    )

    # **And right out, which is where the wrong drawing shows.** Below z11 the
    # preview has no finer level to fall back to, so a screen tile covers 64 of
    # the ones it holds; filling it whole would paint about 4,200 km2 for each
    # tile the selection touches, against the 790 km2 the selection is.
    page.evaluate(with_map("() => __MAP__.setZoom(8)"))
    page.wait_for_timeout(2500)
    far, said_far, sentence_far = painted_ground(page)
    out.append(
        Reading(
            "and zoomed right out it still is",
            far <= said_far * 1.5,
            True,
            note=f"{far:.0f} km2 painted, {said_far:.0f} km2 said",
        )
    )

    # A corner, dragged with a finger, is a different piece of ground. Driven at
    # z12, where all four are on the screen at once.
    page.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 12)"))
    page.wait_for_timeout(1200)
    before = counted_now(page)
    spot = page.evaluate(
        """() => {
            const handle = document.querySelector('.trails-offline-handle');
            if (!handle) { return null; }
            const box = handle.getBoundingClientRect();
            return {x: box.left + box.width / 2, y: box.top + box.height / 2};
        }"""
    )
    dragged = None
    if spot:
        page.mouse.move(spot["x"], spot["y"])
        page.mouse.down()
        # Out and down, so the area grows: a drag that happened to make it
        # smaller would read the same as a drag that did nothing at all.
        page.mouse.move(spot["x"] - 120, spot["y"] + 90, steps=12)
        page.mouse.up()
        dragged = counted_now(page, after=before["at"])["tiles"]
    out.append(Reading("a corner has a handle to drag", bool(spot), True))
    out.append(
        Reading(
            "and dragging it is a different piece of ground",
            bool(dragged and dragged > before["tiles"]),
            True,
            note=f"{before['tiles']} tiles then {dragged}",
        )
    )

    # And a zoom nobody may have cannot be pressed. The whole map stops at z16
    # because that *is* the budget; everything above it would be an archive.
    page.evaluate("async () => await window.trailsOffline.choose('all', 16)")
    page.wait_for_function(
        "() => { const s = window.trailsOffline.state(); return s && s.counted && s.counted.scope === 'all'; }",
        timeout=120_000,
    )
    locks = page.evaluate(
        """() => {
            const out = {};
            document.querySelectorAll('.trails-offline-zoom').forEach(b => {
                out[b.getAttribute('data-zoom')] = {off: !!b.disabled, why: b.title};
            });
            return out;
        }"""
    )
    shut = sorted(at for at, how in locks.items() if how["off"])
    out.append(Reading("the zooms that would be an archive are shut", shut, ["17", "18"], note=str(locks.get("17", {}).get("why"))))
    out.append(Reading("and every zoom that fits the budget is open", [at for at in ("14", "15", "16") if locks.get(at, {}).get("off")], []))
    # Held rather than painted on: a button drawn `disabled` proves what the
    # screen does, and this proves what is true underneath it.
    clamped = page.evaluate("async () => (await window.trailsOffline.choose('all', 18)).zoom")
    out.append(Reading("and asking for one anyway comes back with one that fits", clamped, 16))
    # **Waited for, and read once.** Choosing throws the count away and the panel
    # says *working out how much that is* until the tick that does it lands;
    # asking twice reads one side of that and reports the other.
    page.wait_for_function("() => { const s = window.trailsOffline.state(); return s && s.counted; }", timeout=120_000)
    against = page.evaluate("() => (document.querySelector('.trails-offline-budget') || {}).textContent || ''")
    out.append(Reading("the panel says what the selection costs against the budget", "of the budget" in against, True, note=against))
    return out


def the_map_opens_with_the_network_off(browser: Any, page_path: pathlib.Path) -> list[Check]:
    """The map, served by its own worker, with the network switched off.

    **Today it does not open at all.** The document is served `max-age=300`, so
    five minutes after a visit the browser must revalidate, and offline a
    revalidation fails. Everything the map needs is already inside it -- measured,
    reading a chain's whole elevation profile costs zero requests and so does
    routing -- so the only thing between a reader and an offline map was the
    document itself.

    Two visits, in one context so the worker survives between them: the first
    registers it and it keeps what is open, the second is made with the network
    off and has to be answered from the cache.

    Args:
        browser: The browser to open a fresh context in.
        page_path: The built page, whose directory is what gets served.

    Returns:
        Two checks: what the worker kept and what opened without a network, and
        then the terrain the reader asked it to keep.
    """
    with served(page_path.parent) as origin:
        address = f"{origin}/{page_path.name}"
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        # **Counted before any page script runs**, which is the only place a
        # wrapper can see every timer the page arms. A tick behind a locked
        # screen is the cheapest way to spend a battery on nothing, and the one
        # a page can acquire without anybody noticing.
        context.add_init_script(
            """window.__trailsIntervals = [];
            const armed = window.setInterval;
            window.setInterval = function (fn, ms) {
                window.__trailsIntervals.push(ms || 0);
                return armed.apply(this, arguments);
            };"""
        )
        first = context.new_page()
        first.goto(address, timeout=180_000)
        # **Waiting rather than sleeping**, which this suite says about itself
        # and had stopped doing twice already. Two settles of twenty seconds took
        # the run from 180 to 315; the page says when it is ready.
        first.wait_for_function("() => window.trailsWorker", timeout=120_000)
        registered = first.evaluate("() => window.trailsWorker")
        kept = True
        try:
            first.wait_for_function(CACHED_PAGE, timeout=60_000)
        except Exception:
            kept = False
        # Move, so that some terrain is asked for while the worker is in the way
        # of it. The tiles the first paint fetched went out before it took over.
        first.evaluate("() => window[Object.keys(window).find(k => k.startsWith('map_'))].setZoom(10)")
        first.wait_for_timeout(4000)
        tiles = first.evaluate("async () => (await (await caches.open('trails-tiles')).keys()).length")
        # **What the first visit paid**, read off the server rather than the
        # page: the worker keeps the map by asking for it a second time, and if
        # that second ask crossed the wire the first visit would cost twice.
        fetched = _Quiet.asked.get(f"/{page_path.name}", 0)

        # ---- a newer map, found without navigating --------------------------
        # **The one the reader could not reach.** The check for a new map lives
        # in `pageFor`, which runs on a navigation, so the only way to hear about
        # one was to reload -- the very thing the message then asks for -- and a
        # home-screen app has no reload control. Driven by moving the file's
        # mtime, which is what `Last-Modified` is served from and what the worker
        # compares.
        newer: list[Reading] = []
        before_tiles = first.evaluate("async () => (await (await caches.open('trails-terrain')).keys()).length")
        page_path.touch()
        got_before = _Quiet.asked.get(f"/{page_path.name}", 0)
        first.evaluate("() => { navigator.serviceWorker.controller.postMessage({trails: 'check'}); }")
        found = True
        try:
            first.wait_for_selector(".trails-newer", timeout=30_000)
        except Exception:
            found = False
        newer.append(Reading("a newer map is found without a navigation", found, True))
        newer.append(
            Reading(
                "and the line carries a button to act on it",
                first.evaluate("() => !!document.querySelector('.trails-newer-reload')"),
                True,
                note="installed to a home screen there is no other way to reload",
            )
        )
        # **And the HEAD is what it cost.** Asking with a GET would spend 5.2 MB
        # to be told nothing had happened, every time somebody came back to the
        # app. The body is fetched only because it did move.
        newer.append(
            Reading(
                "the check asked with HEAD before the body",
                _Quiet.heads.get(f"/{page_path.name}", 0),
                1,
                note=f"{_Quiet.asked.get(f'/{page_path.name}', 0)} GETs in the whole visit",
            )
        )
        newer.append(
            Reading(
                "and finding one costs the terrain nothing",
                first.evaluate("async () => (await (await caches.open('trails-terrain')).keys()).length"),
                before_tiles,
            )
        )
        # **And it costs the page nothing either.** Finding a newer map used to
        # fetch it: 5.2 MB spent behind the reader, over whatever connection
        # happened to be attached, for a reload they might never press. The body
        # is now the button's job, so looking is the HEAD above and nothing more.
        newer.append(
            Reading(
                "and looking does not fetch the map",
                _Quiet.asked.get(f"/{page_path.name}", 0),
                got_before,
                note="the body is what the Reload button spends",
            )
        )

        # **And a body that breaks mid-stream leaves the old map alone.** This
        # is the property the Reload button rests on: `fetch` resolves when the
        # headers arrive, so `answer.ok` is true while five megabytes are still
        # coming, and the signal going is therefore a failure *inside*
        # `cache.put`. Driven against a stream that errors after a few bytes,
        # which is what the Cache API sees either way.
        #
        # Firefox on Linux, like everything else here: it measures the API's
        # rule, not WebKit's implementation of it.
        atomic = first.evaluate(
            """async () => {
                const name = 'trails-atomic-probe';
                const cache = await caches.open(name);
                const url = new URL('probe', location.href).href;
                await cache.put(url, new Response('the map you already had'));
                let threw = false;
                try {
                    const broken = new ReadableStream({
                        start(control) {
                            control.enqueue(new TextEncoder().encode('half of a newer map'));
                            control.error(new Error('the signal went'));
                        }
                    });
                    await cache.put(url, new Response(broken));
                } catch (stopped) { threw = true; }
                const held = await cache.match(url);
                const still = held ? await held.text() : null;
                await caches.delete(name);
                return {threw: threw, still: still};
            }"""
        )
        newer.append(Reading("a body that breaks mid-stream is not written at all", atomic["threw"], True))
        newer.append(
            Reading(
                "and what stays is the map that was already there",
                atomic["still"],
                "the map you already had",
                note="no half-written entry, so Reload cannot leave a broken copy",
            )
        )

        # ---- and in the foreground it asks for nothing ----------------------
        # **Stated absolutely rather than as a budget**, which is what makes it
        # checkable: once the page has loaded, sitting in front of it and coming
        # back to it cost no requests at all. Coming back used to cost a HEAD
        # every ten minutes and, whenever the answer was yes, the map behind it.
        # Driven by faking the visibility change the page listens for -- the same
        # event a home-screen app gets when it is reopened.
        idle: list[Reading] = []
        first.wait_for_timeout(3000)
        seen: list[str] = []
        first.on("request", lambda request: seen.append(request.url))
        first.evaluate(
            """async () => {
                const swap = (state) => {
                    Object.defineProperty(document, 'visibilityState', {value: state, configurable: true});
                    document.dispatchEvent(new Event('visibilitychange'));
                };
                for (let i = 0; i < 2; i += 1) {
                    swap('hidden');
                    await new Promise(r => setTimeout(r, 400));
                    swap('visible');
                    await new Promise(r => setTimeout(r, 400));
                }
            }"""
        )
        first.wait_for_timeout(3000)
        idle.append(
            Reading(
                "coming back to the app costs no request at all",
                len(seen),
                0,
                note="; ".join(url.rsplit("/", 1)[-1] for url in seen[:4]) or "two rounds of hidden and visible",
            )
        )
        armed = first.evaluate("() => window.__trailsIntervals || []")
        # **And the way to act on it is reachable without the offline tool.** A
        # map goes stale because an installed app resumes instead of navigating,
        # which is true whatever the switch says -- so the check cannot live only
        # behind a feature a reader may never turn on. `Sources` is the panel
        # about the page, and it carries the same row.
        first.evaluate("() => window.trailsChrome.open('info')")
        first.wait_for_timeout(600)
        newer.append(
            Reading(
                "the map's age is in Sources too, not only behind Offline",
                first.evaluate(
                    "() => { const node = document.querySelector('.trails-dock .trails-offline-age');"
                    " return node ? node.textContent.indexOf('This map was built') === 0 : false; }"
                ),
                True,
            )
        )
        newer.append(
            Reading(
                "and the button with it",
                first.evaluate("() => !!document.querySelector('.trails-dock .trails-offline-check')"),
                True,
            )
        )
        # **What the page says opening it cost.** No check here can measure the
        # device this map is carried on -- an installed app reported ten to
        # twenty seconds where this run measures under two -- so the page keeps
        # its own account and `Sources` reads it out. Driven for the shape of the
        # sentence, not the figures: those belong to whatever opened it.
        said_cost = first.evaluate("() => (document.querySelector('.trails-dock .trails-open-cost') || {}).textContent || ''")
        cost = first.evaluate("() => window.trailsOpened.cost()")
        newer.append(
            Reading(
                "the page says what opening it cost",
                said_cost.startswith("Opened in ") and "document" in said_cost,
                True,
                note=said_cost[:120],
            )
        )
        newer.append(
            Reading(
                "and the map's own build is a figure in it",
                cost["build"] is not None and cost["build"] > 0,
                True,
                note=f"{cost['build']} ms building, {cost['parse']} ms parsing, {cost['bytes'] / 1e6:.1f} MB",
            )
        )
        first.evaluate("() => window.trailsChrome.close()")
        idle.append(
            Reading(
                "and nothing is left ticking behind it",
                len(armed),
                0,
                note=f"delays: {armed}" if armed else "no interval armed by the page",
            )
        )
        first.evaluate("() => { Object.defineProperty(document, 'visibilityState', {value: 'visible', configurable: true}); }")

        # ---- and the terrain a reader asked for, in the same session ---------
        # **In this page and not in one of its own**, because a second 15.6 MB
        # document is a minute of loading and about 590 MB of memory. The two
        # things being driven here need the same worker and the same origin, so
        # they are one visit that answers twice.
        terrain: list[Reading] = []
        first.wait_for_function("() => window.trailsOffline", timeout=60_000)
        opened = first.evaluate("async () => await window.trailsOffline.refresh()")
        terrain.append(Reading("the panel knows this browser can keep it", opened["available"], True, note=str(opened.get("why"))))

        # **On, with nothing kept, opens the chooser instead**: a switch that
        # answers with a blank map is a switch that lied.
        asked = first.evaluate("async () => { var s = await window.trailsOffline.toggle(true); return {on: s.on, chooser: s.chooser}; }")
        terrain.append(Reading("switching it on with nothing kept asks first", asked["chooser"], True))
        terrain.append(Reading("and does not claim to be on", asked["on"], False))

        # **A run that keeps nothing must switch nothing on.** Driven with the
        # context offline, which is the case this actually happens in: every
        # fetch fails, the loop finishes, and turning the switch on there hands
        # over exactly the blank map the chooser exists to prevent. It did, and
        # it is driven here rather than later because the cache is empty at this
        # point anyway -- a `forget()` in the middle of this check would take
        # away the terrain the offline visit below has to draw.
        #
        # **Twice, because there are two ways to have no connection** and the
        # page answers them differently. Honestly offline it does not begin at
        # all: a hundred thousand fetches into a dead radio is the most
        # expensive thing this page could do, in the situation where the battery
        # is the whole question.
        SAID = "() => (document.querySelector('.trails-offline-figures') || {}).textContent || ''"
        first.evaluate(KEEP_AREA, KEPT_AREA)
        context.set_offline(True)
        first.evaluate("() => window.trailsOffline.keep()")
        first.wait_for_function("() => !window.trailsOffline.state().busy", timeout=180_000)
        starved = first.evaluate("() => window.trailsOffline.state()")
        terrain.append(Reading("with no connection the run is not begun", "No connection" in first.evaluate(SAID), True))
        terrain.append(Reading("and it keeps nothing", starved["kept"]["tiles"], 0))
        terrain.append(Reading("and switches nothing on", starved["on"], False))

        # **And now the case the flag gets wrong.** `navigator.onLine` reports
        # true for any live interface, so on a mountain with one bar and no route
        # it says online and the guard above waves the run through -- which is
        # what the twelve-in-a-row rule behind it is for. Driven by forcing the
        # flag true while the context is offline, which is that valley exactly.
        first.evaluate("() => { Object.defineProperty(navigator, 'onLine', {value: true, configurable: true}); }")
        first.evaluate("() => window.trailsOffline.keep()")
        first.wait_for_function("() => !window.trailsOffline.state().busy", timeout=180_000)
        context.set_offline(False)
        first.evaluate("() => { delete navigator.onLine; }")
        stalled = first.evaluate("() => window.trailsOffline.state()")
        # The sentence exists on no other path: it is written only where the run
        # gave up on the connection rather than reaching the end of the list.
        terrain.append(
            Reading(
                "a run whose connection dies gives up rather than grinding on",
                "The connection gave out" in first.evaluate(SAID),
                True,
                note="twelve refusals in a row, not a hundred thousand attempts",
            )
        )
        terrain.append(Reading("and it too keeps nothing", stalled["kept"]["tiles"], 0))
        terrain.append(Reading("and switches nothing on either", stalled["on"], False))

        # **What the chooser draws, before anything is downloaded.** It needs the
        # network for the terrain under the preview and the switch still off, and
        # both are true here and neither is once the download below has run.
        first.evaluate("async () => await window.trailsOffline.open(true)")
        first.evaluate(KEEP_AREA, KEPT_AREA)
        first.wait_for_function("() => { const s = window.trailsOffline.state(); return s && s.counted; }", timeout=60_000)
        terrain.extend(what_the_chooser_draws(first))

        # A small, real download: the area set above, at the coarsest zoom the
        # chooser offers, is a few hundred tiles from Kartverket -- a check and
        # not a bulk fetch. **Zoomed in first**, and the two asks below are z14
        # and z15 rather than z12 and z13: the chooser floors at z14, so two asks
        # under it would clamp to the same set, the second run would skip every
        # tile as already kept, and the regression it exists for -- a download
        # made *through* the worker with the switch on -- would never happen.
        #
        # Set again rather than assumed: the check above drags one of its corners
        # on purpose, and what is kept here has to be the ground the offline
        # visit at the bottom looks at.
        first.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 14)"))
        first.wait_for_timeout(1500)
        first.evaluate(KEEP_AREA, KEPT_AREA)
        first_ask = first.evaluate("() => window.trailsOffline.needed()")
        RAIL_OFFLINE = "() => (document.querySelector('.trails-rail [data-tool=offline] svg') || {}).innerHTML"
        drawn_off = first.evaluate(RAIL_OFFLINE)
        first.evaluate("() => window.trailsOffline.keep()")
        first.wait_for_function("() => !window.trailsOffline.state().busy", timeout=180_000)
        after = first.evaluate("() => window.trailsOffline.state()")
        terrain.append(Reading("what it said it would keep is what it kept", after["kept"]["tiles"], first_ask["tiles"]))
        terrain.append(Reading("and the switch is on once it is there", after["on"], True))
        # **And the row says so without being opened.** The switch is thrown
        # inside this panel, which on a phone is covering the menu at the time,
        # so the drawing behind it has to have followed by the time the reader
        # closes the panel. Two drawings sharing a tray: the arrow becomes a
        # tick.
        drawn_on = first.evaluate(RAIL_OFFLINE)
        terrain.append(Reading("and the tool's drawing followed it", bool(drawn_off) and drawn_on != drawn_off, True, note="the arrow became a tick"))

        # **The one that would have been silent.** With the switch already on,
        # a second download goes out through a worker that answers unkept tiles
        # with a blank -- unless it lets `cache: 'reload'` past. Without that
        # branch every one of these is 68 bytes of transparent PNG written into
        # the terrain cache as terrain, and the panel reports success.
        first.evaluate("async () => await window.trailsOffline.choose('draw', 15)")
        second_ask = first.evaluate("() => window.trailsOffline.needed()")
        # **The panel has to be on the screen to be read.** Its holder is left
        # detached until the dock puts it somewhere — the same seam `Where I am`
        # and `Sources` use — so `querySelector` finds nothing while the tool is
        # shut, and a check reading it would report the run was over before it
        # started. Every step around this one drives the API instead, which is
        # why it never came up.
        # **Started without being waited on.** `keep` returns the run's own
        # promise and `evaluate` awaits whatever it is handed, so asking for it
        # the usual way does not return until the download is finished — and the
        # reading below, which is about a figure that only exists mid-run, then
        # measures a run that is over. The braces are what make it undefined.
        first.evaluate("() => { window.trailsOffline.keep(); }")
        # **Read while it is running, because that is the only time it exists.**
        # The claim is that a resumed run opens at what is already kept rather
        # than at zero — which is a frame of the panel and not a figure any API
        # reports. Polled rather than slept on: the first draw lands once
        # `keys()` has answered, and that is a different moment on every machine.
        # **Asked of the state and not of the panel.** The figure lives in one
        # line of a holder that is detached until the dock shows it, and a run of
        # a few hundred tiles is over in under a second — two ways for a check to
        # read nothing and call it a pass.
        first.wait_for_function("() => !window.trailsOffline.state().busy", timeout=180_000)
        # **What a resumed run downloads, which is the claim that matters.** It
        # used to be asked as *does the counter open at the resumed figure*, and
        # the pre-scan that made that true was `cache.keys()` over the whole
        # terrain cache — one `Request` object per tile, 131,033 of them for the
        # whole map at z16, at the moment the page can least afford it. The
        # counter now climbs from zero through what it already holds; what has
        # to stay true is that it fetches none of it.
        resumed = first.evaluate("() => window.trailsOffline.state().run")
        terrain.append(
            Reading(
                "a resumed run fetches nothing it already holds",
                resumed["held"],
                first_ask["tiles"],
                note=f"{resumed['added']} fetched, {resumed['held']} found already there",
            )
        )
        weighed = first.evaluate(
            """async () => {
                const cache = await caches.open('trails-terrain');
                const keys = (await cache.keys()).filter(k => k.url.indexOf('trails.invalid') === -1);
                let smallest = Infinity, total = 0;
                for (const key of keys.slice(0, 40)) {
                    const body = await (await cache.match(key)).arrayBuffer();
                    smallest = Math.min(smallest, body.byteLength);
                    total += body.byteLength;
                }
                return {kept: keys.length, smallest: smallest, sampled: Math.min(40, keys.length)};
            }"""
        )
        terrain.append(
            Reading(
                "the second ask is more ground than the first",
                second_ask["tiles"] > first_ask["tiles"],
                True,
                note=f"{first_ask['tiles']} then {second_ask['tiles']}",
            )
        )
        terrain.append(Reading("keeping more while it is on keeps all of it", weighed["kept"], second_ask["tiles"]))
        # A blank tile is 68 bytes. Anything Kartverket drew is thousands.
        terrain.append(
            Reading(
                "and every kept tile is terrain, not a blank",
                weighed["smallest"] > 1000,
                True,
                note=f"smallest of {weighed['sampled']}: {weighed['smallest']} B",
            )
        )
        # **What lies past the finest level anybody kept.** The download above
        # went to z15, so z16 is ground the reader owns nothing of -- and the
        # question is what the map does when they keep zooming. Leaflet does not
        # scale a coarse tile up to cover a fine one: `maxNativeZoom` is 18 on
        # both sheets, so it asks for the real z16, the worker has none, and with
        # the switch on it answers a blank rather than the network. Measured on
        # the very ground that is kept, one level apart, so the only thing that
        # differs between the two readings is the zoom.
        COUNT = """() => {
            let good = 0, blank = 0;
            document.querySelectorAll('img.leaflet-tile').forEach(img => {
                if (img.naturalWidth > 1) { good += 1; } else { blank += 1; }
            });
            return {good: good, blank: blank};
        }"""
        # **Driven with the network off**, which makes these three readings say
        # more than the zoom. The token on the sheet's URL moved when the switch
        # went on, so anything that draws here is a kept tile answered under its
        # new address off the device -- the invariant the token has to satisfy or
        # it would be a re-download dressed as a fix.
        context.set_offline(True)
        first.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 15)"))
        first.wait_for_timeout(3000)
        at_top = first.evaluate(COUNT)
        first.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 16)"))
        first.wait_for_timeout(3000)
        past_top = first.evaluate(COUNT)
        terrain.append(
            Reading(
                "at the finest level kept, the ground draws with the network off",
                at_top["good"] > 0,
                True,
                note=f"{at_top['good']} drawn, {at_top['blank']} blank at z15 — under the moved token",
            )
        )
        # **And one level past it, that same ground magnified.** Left alone,
        # Leaflet asks Kartverket for the real z16, the worker has none and
        # answers a blank -- a valid 200, so Leaflet counts it loaded and prunes
        # the z15 the reader does own. Measured at 0 drawn against 35 blank
        # before `fitNativeZoom` held the ceiling to what is on the device.
        terrain.append(
            Reading(
                "and one level past it the kept ground is magnified, not dropped",
                past_top["good"] > 0,
                True,
                note=f"{past_top['good']} drawn, {past_top['blank']} blank at z16 — z15 doubled",
            )
        )
        terrain.append(
            Reading(
                "and the ceiling is the finest level held, not the sheet's own",
                first.evaluate(
                    with_map(
                        "() => { let seen = null; __MAP__.eachLayer(l => { if (l.getTileUrl) { seen = l.options.maxNativeZoom; } }); return seen; }"
                    )
                ),
                15,
                note="both sheets are built with 18",
            )
        )
        context.set_offline(False)
        first.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 14)"))
        first.wait_for_timeout(1500)

        # **And the switch is what stops the fetch, not a missing network.** The
        # whole point of being able to turn it on indoors is to see coverage
        # before walking out; if the network were what was answering, this would
        # be untested and nobody would know until a valley. Driven online, on
        # ground nobody kept.
        first.evaluate(with_map("() => __MAP__.setView([65.30, 12.40], 12)"))
        first.wait_for_timeout(3000)
        indoors = first.evaluate(
            """() => {
                let good = 0, blank = 0;
                document.querySelectorAll('img.leaflet-tile').forEach(img => {
                    if (img.naturalWidth > 1) { good += 1; } else { blank += 1; }
                });
                return {good: good, blank: blank};
            }"""
        )
        terrain.append(Reading("with the switch on, unkept ground stays blank even online", indoors["good"], 0, note=f"{indoors['blank']} blank"))
        # **And turning the switch off keeps every tile.** Nothing about the
        # switch is a deletion -- it is a flag in `localStorage` and a message to
        # the worker -- and the only thing in this page that empties a tile cache
        # is the Delete button, behind a confirmation. Worth a reading because it
        # is the kind of thing a later tidy-up breaks silently: somebody frees
        # the space on the way out, and a reader who switched off in a hotel to
        # see live terrain walks out with nothing.
        held = first.evaluate("() => window.trailsOffline.state().kept.tiles")
        parked = first.evaluate("async () => { await window.trailsOffline.toggle(false); return window.trailsOffline.state(); }")
        terrain.append(Reading("switching it off keeps every tile", parked["kept"]["tiles"], held))
        terrain.append(Reading("and it really is off", parked["on"], False))
        # And the ceiling goes back to what the sheet was built with, so a reader
        # who switched off for live terrain gets the real fine levels again.
        terrain.append(
            Reading(
                "and the zoom ceiling is the sheet's own again",
                first.evaluate(
                    with_map(
                        "() => { let seen = null; __MAP__.eachLayer(l => { if (l.getTileUrl) { seen = l.options.maxNativeZoom; } }); return seen; }"
                    )
                ),
                18,
                note="held to 15 while it was on",
            )
        )
        # The mirror of the reading above: with the switch off, the ground nobody
        # kept comes from the network again, on the same view that was blank a
        # moment ago.
        first.wait_for_timeout(4000)
        live = first.evaluate(
            """() => {
                let good = 0, blank = 0;
                document.querySelectorAll('img.leaflet-tile').forEach(img => {
                    if (img.naturalWidth > 1) { good += 1; } else { blank += 1; }
                });
                return {good: good, blank: blank};
            }"""
        )
        terrain.append(
            Reading(
                "and unkept ground draws again from the network",
                live["good"] > 0,
                True,
                note=f"{live['good']} drawn where {indoors['blank']} were blank with the switch on",
            )
        )
        first.evaluate("async () => { await window.trailsOffline.toggle(true); }")
        first.wait_for_timeout(1000)

        # **Asked while it is still open**, because this is what the offline page
        # is held against. Panning and the switch above do not touch it: the
        # count is over the map's layers, not over what is in view.
        online = first.evaluate(WHOLE_MAP)
        first.close()

        context.set_offline(True)
        second = context.new_page()
        thrown: list[str] = []
        second.on("pageerror", lambda error: thrown.append(str(error)))
        second.goto(address, timeout=180_000)
        second.wait_for_function(with_map("() => {" + DRAWN + " return drawn.length > 11000; }"), timeout=120_000)
        offline = second.evaluate(WHOLE_MAP)
        # And with the network off, what was kept is what is drawn: the tiles
        # come back from the cache and none of them is the worker's blank. **On
        # the ground it was kept for**, which is the part that has to be said:
        # the terrain above was drawn as a rectangle round 65.55 N 13.05 E, and
        # looking somewhere else asks for ground nobody kept and is answered,
        # correctly, with blanks.
        second.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 14)"))
        second.wait_for_timeout(3000)
        drawn_terrain = second.evaluate(
            """() => {
                let good = 0, blank = 0;
                document.querySelectorAll('img.leaflet-tile').forEach(img => {
                    if (img.naturalWidth > 1) { good += 1; } else { blank += 1; }
                });
                return {good: good, blank: blank};
            }"""
        )
        # Read before anything is drawn: the switch is held in localStorage and
        # re-told to the worker on load, and the worker keeps its own copy in the
        # terrain cache because it is stopped and started around single fetches.
        reloaded = second.evaluate("async () => await window.trailsOffline.refresh()")
        terrain.append(Reading("the switch survives a reload", reloaded["on"], True))
        terrain.append(Reading("and so does the terrain", reloaded["kept"]["tiles"], second_ask["tiles"]))

        terrain.append(Reading("offline, the kept ground draws", drawn_terrain["good"] > 0, True, note=f"{drawn_terrain['good']} tiles"))
        terrain.append(Reading("and none of it is a broken image", drawn_terrain["blank"], 0))

        # **And ground nobody kept is blank rather than broken**, which is the
        # other half of the same design: offline the worker answers an unkept
        # tile with a 1x1 transparent PNG so Leaflet draws the page's own ground
        # instead of a torn image over it.
        second.evaluate(with_map("() => __MAP__.setView([65.55, 13.05], 11)"))
        second.wait_for_timeout(3000)
        unkept = second.evaluate(
            """() => {
                let blank = 0, tiles = 0;
                document.querySelectorAll('img.leaflet-tile').forEach(img => {
                    tiles += 1;
                    if (img.naturalWidth <= 1) { blank += 1; }
                });
                return {tiles: tiles, blank: blank};
            }"""
        )
        terrain.append(
            Reading("ground that was not kept comes back blank", unkept["blank"] > 0, True, note=f"{unkept['blank']} of {unkept['tiles']}")
        )
        terrain.append(Reading("and still threw nothing", len(thrown), 0, note="; ".join(thrown[:2])))
        # And the reader can have the space back from inside the thing that took
        # it, which is the last of the four this panel is for.
        emptied = second.evaluate("async () => { var s = await window.trailsOffline.forget(); return {tiles: s.kept.tiles, on: s.on}; }")
        terrain.append(Reading("and it can all be deleted again", emptied["tiles"], 0))
        terrain.append(Reading("which switches offline mode back off", emptied["on"], False))

        context.set_offline(False)
        context.close()

    return [
        Check(
            "the map opens with the network off",
            [
                Reading("a worker is registered", bool(registered and registered.get("kept")), True, note=str(registered)),
                Reading("and the page is in its cache", kept, True),
                # Kept on the **first** visit, and for one download: `cache.add`
                # goes through the browser's own cache, which was handed the map
                # seconds earlier. Two would be the whole point undone.
                Reading("the first visit downloads the map once", fetched, 1),
                # The browser's own cache already keeps a tile five days --
                # `max-age=432000`, measured -- so this is for the walk somebody
                # plans a fortnight out, not for the next minute.
                Reading("terrain it was shown is kept too", tiles > 0, True, note=f"{tiles} tiles"),
                Reading("nothing threw with the network off", len(thrown), 0, note="; ".join(thrown[:2])),
                # The whole map, not a shell of one: every line, every marker, and
                # the graph that routes over them.
                Reading("offline: paths drawn", offline["paths"], online["paths"], note=f"{online['paths']} online"),
                Reading("offline: markers", offline["markers"], online["markers"], note=f"{online['markers']} online"),
                Reading("offline: the routing graph is there", offline["graph"], True),
            ],
        ),
        Check("a newer map, found without navigating", newer),
        Check("what the page costs while nobody touches it", idle),
        Check("the terrain a reader asked to keep", terrain),
    ]


def drive(page: Any) -> list[Check]:
    """Run every check in one browser session.

    Args:
        page: A page already loaded and settled

    Returns:
        Every check, in the order it ran
    """
    checks = [check(page) for check in (furniture, the_icons_are_there, map_wheel, chrome_layout, the_profile_tool) if wanted(check)]
    if wanted(the_zoom_the_scale_says):
        checks.append(the_zoom_the_scale_says(page))

    if not select(page, LONG_CHAIN):
        checks.append(Check("the profile panel", skipped=f"{LONG_CHAIN} is not in this page — see LONG_CHAIN"))
        return checks

    if wanted(sea_level):
        checks.append(sea_level(page))
    if wanted(crosshair_mark):
        checks.append(crosshair_mark(page))
    if wanted(curve_wheel):
        checks.append(curve_wheel(page, zoomable=True))
    if wanted(true_scale):
        checks.append(true_scale(page))
    if wanted(zoom_ceiling):
        checks.append(zoom_ceiling(page))
    if wanted(brushing_the_curve):
        checks.append(brushing_the_curve(page))
    if wanted(reading_with_a_finger):
        checks.append(reading_with_a_finger(page))
    if wanted(pinch_the_curve):
        checks.append(pinch_the_curve(page))
    if wanted(a_way_back_to_the_whole):
        checks.append(a_way_back_to_the_whole(page))
    if wanted(room_on_a_short_screen):
        checks.append(room_on_a_short_screen(page))
    if wanted(narrow_sheets):
        checks.append(narrow_sheets(page))
    if wanted(the_sources_behind_an_i):
        checks.append(the_sources_behind_an_i(page))
    if wanted(the_theme_switch):
        checks.append(the_theme_switch(page))
    select(page, LONG_CHAIN)

    # A chain already drawn finer than its own samples, which is 99 % of them:
    # there the wheel belongs to the map and the chart must not touch it.
    short = page.evaluate(
        with_map(
            """(long) => {"""
            + DRAWN
            + """ for (const layer of chained) {
                    const cls = layer.options.className;
                    if (cls !== long) { return cls; } }
                  return null; }"""
        ),
        LONG_CHAIN,
    )
    if short and select(page, short):
        if page.evaluate("() => { const v = window.trailsProfilePanel.view(); return v && v.closest <= 1.001; }"):
            if wanted(curve_wheel):
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

    if wanted(popup_click):
        checks.append(popup_click(page))
    if wanted(stations_and_list):
        checks.append(stations_and_list(page, places))
    if wanted(a_finger_can_use_it):
        checks.append(a_finger_can_use_it(page))
    if wanted(the_plan_bar):
        checks.append(the_plan_bar(page))
    if wanted(the_point_list_takes_the_room):
        checks.append(the_point_list_takes_the_room(page))
    if wanted(undo_undoes_the_last_change):
        checks.append(undo_undoes_the_last_change(page))
    if wanted(files_from_the_page):
        checks.append(files_from_the_page(page))
    if wanted(a_click_is_not_a_pan):
        checks.append(a_click_is_not_a_pan(page))
    if wanted(the_search_on_a_narrow_panel):
        checks.append(the_search_on_a_narrow_panel(page))
    if wanted(sharing_the_room):
        checks.append(sharing_the_room(page))
    if wanted(where_the_reader_is):
        checks.append(where_the_reader_is(page))
    if wanted(the_dark_set):
        checks.append(the_dark_set(page))
    # **Last, because it reloads the page.** Everything after it would be
    # reading a page in a state nothing before it had set up.
    if wanted(a_plan_survives_a_reload):
        checks.append(a_plan_survives_a_reload(page))
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
    parser.add_argument("--only", default="", help="Run only the checks whose name holds this word")
    parser.add_argument("--headed", action="store_true", help="Show the browser rather than hiding it")
    parser.add_argument("--json", action="store_true", help="Print the readings as JSON as well")
    args = parser.parse_args()

    page_path = pathlib.Path(args.page)
    if not page_path.exists():
        print(f"no page at {page_path} — run `command make map` first", file=sys.stderr)
        return 1

    from playwright.sync_api import sync_playwright

    global ONLY
    ONLY = args.only
    print(f"driving {page_path} ({page_path.stat().st_size / 1e6:.2f} MB)" + (f" -- only {ONLY}" if ONLY else ""))
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=not args.headed)
        # **A position is granted here or it cannot be driven at all.** The
        # browser asks the reader, and a driven browser has no reader; Playwright
        # answers for one. Somewhere inside the drawn park, so the check can ask
        # whether the map moved to it.
        page = browser.new_page(
            viewport={"width": 1400, "height": 900},
            permissions=["geolocation"],
            geolocation={"latitude": 65.55, "longitude": 13.05, "accuracy": 24},
        )
        # **Everything this page does is in one script block**, so one syntax
        # error anywhere in it stops all of it -- and every check below then
        # fails at once, saying which behaviour is missing and never why. It
        # cost a build: a `\n` written into a template where `\\n` was meant
        # became a real line break inside a JavaScript string, and the whole map
        # was a blank grey box with 11,589 paths that never existed.
        thrown: list[str] = []
        page.on("pageerror", lambda error: thrown.append(str(error)))
        # A 40 MB page is 25 seconds of parsing on a good day, and the
        # default 30 is a margin thin enough to fail on a busy machine -- which
        # reads as a broken run rather than as the slow load it is.
        page.goto(page_path.resolve().as_uri(), timeout=120_000)
        page.wait_for_timeout(SETTLE_MS)
        checks = [Check("the page ran at all", [Reading("errors thrown while loading", len(thrown), 0, note="; ".join(thrown[:2]))])]
        if thrown:
            browser.close()
            return report(checks)
        page.evaluate("() => window.trailsGraph.ready")
        checks += drive(page)
        # **Last, and in a context of its own.** A service worker outlives the
        # page that registered it and would answer for every check after it.
        #
        # And the driven page is closed first, which is not tidiness: this page
        # costs about 590 MB settled, and a second one beside it took the browser
        # down mid-load -- `TargetClosedError` at the first wait, with nothing
        # said about why. Two 42 MB documents at once is not a thing to ask for.
        if wanted(the_map_opens_with_the_network_off):
            page.close()
            checks.extend(the_map_opens_with_the_network_off(browser, page_path))
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
