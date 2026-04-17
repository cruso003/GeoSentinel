"""SNAP GPT graph for Sentinel-1 TOPS interferogram processing (Spec §11.5).

Produces an XML that `gpt` consumes. Stages:
  Read(master) → Read(slave) → TOPSAR-Split → Apply-Orbit-File → Back-Geocoding
    → Enhanced-Spectral-Diversity → Interferogram → TOPSAR-Deburst
    → Topo-Phase-Removal → Goldstein-Phase-Filtering → Subset → Write(BEAM-DIMAP)

The unwrap step runs as a separate SNAPHU call outside of this graph (SNAP
shells out to SNAPHU with a caller-provided config file).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<graph id="geosentinel-s1-insar">
  <version>1.0</version>

  <node id="Read-Master">
    <operator>Read</operator>
    <parameters>
      <file>{master}</file>
    </parameters>
  </node>
  <node id="Read-Slave">
    <operator>Read</operator>
    <parameters>
      <file>{slave}</file>
    </parameters>
  </node>

  <node id="Split-Master">
    <operator>TOPSAR-Split</operator>
    <sources><sourceProduct refid="Read-Master"/></sources>
    <parameters>
      <subswath>{subswath}</subswath>
      <selectedPolarisations>{pol}</selectedPolarisations>
    </parameters>
  </node>
  <node id="Split-Slave">
    <operator>TOPSAR-Split</operator>
    <sources><sourceProduct refid="Read-Slave"/></sources>
    <parameters>
      <subswath>{subswath}</subswath>
      <selectedPolarisations>{pol}</selectedPolarisations>
    </parameters>
  </node>

  <node id="Orbit-Master">
    <operator>Apply-Orbit-File</operator>
    <sources><sourceProduct refid="Split-Master"/></sources>
  </node>
  <node id="Orbit-Slave">
    <operator>Apply-Orbit-File</operator>
    <sources><sourceProduct refid="Split-Slave"/></sources>
  </node>

  <node id="BackGeo">
    <operator>Back-Geocoding</operator>
    <sources>
      <sourceProduct.0 refid="Orbit-Master"/>
      <sourceProduct.1 refid="Orbit-Slave"/>
    </sources>
    <parameters>
      <demName>SRTM 1Sec HGT</demName>
    </parameters>
  </node>

  <node id="ESD">
    <operator>Enhanced-Spectral-Diversity</operator>
    <sources><sourceProduct refid="BackGeo"/></sources>
  </node>

  <node id="Ifg">
    <operator>Interferogram</operator>
    <sources><sourceProduct refid="ESD"/></sources>
    <parameters>
      <subtractFlatEarthPhase>true</subtractFlatEarthPhase>
    </parameters>
  </node>

  <node id="Deburst">
    <operator>TOPSAR-Deburst</operator>
    <sources><sourceProduct refid="Ifg"/></sources>
  </node>

  <node id="TopoRem">
    <operator>TopoPhaseRemoval</operator>
    <sources><sourceProduct refid="Deburst"/></sources>
    <parameters>
      <demName>SRTM 1Sec HGT</demName>
    </parameters>
  </node>

  <node id="Goldstein">
    <operator>GoldsteinPhaseFiltering</operator>
    <sources><sourceProduct refid="TopoRem"/></sources>
  </node>

  <node id="Subset">
    <operator>Subset</operator>
    <sources><sourceProduct refid="Goldstein"/></sources>
    <parameters>
      <geoRegion>{aoi_wkt}</geoRegion>
    </parameters>
  </node>

  <node id="Write">
    <operator>Write</operator>
    <sources><sourceProduct refid="Subset"/></sources>
    <parameters>
      <file>{output}</file>
      <formatName>BEAM-DIMAP</formatName>
    </parameters>
  </node>
</graph>
"""


def render_graph(
    *,
    master: Path,
    slave: Path,
    output: Path,
    aoi_wkt: str,
    subswath: str = "IW2",
    pol: str = "VV",
) -> str:
    return TEMPLATE.format(
        master=master,
        slave=slave,
        output=output,
        aoi_wkt=aoi_wkt,
        subswath=subswath,
        pol=pol,
    )


def run_graph(xml: str, *, gpt_bin: str = "gpt", jvm_mem_mb: int = 8192) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
        fh.write(xml)
        path = fh.name
    return subprocess.run(
        [gpt_bin, "-c", f"{jvm_mem_mb}M", "-q", "4", path],
        check=True, capture_output=True, text=True,
    )
