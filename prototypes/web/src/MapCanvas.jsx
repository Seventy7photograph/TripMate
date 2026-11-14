import { useEffect, useRef, useState } from "react";
import {
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

function routeFeature(stops) {
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: stops.map((stop) => stop.coords),
    },
  };
}

export function MapCanvas({
  stops,
  selectedStopId,
  onSelectStop,
  compact = false,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [106.555, 29.558],
      zoom: 12.2,
      pitch: 0,
      attributionControl: false,
      dragRotate: false,
      touchPitch: false,
    });

    map.addControl(
      new NavigationControl({
        showCompass: false,
        showZoom: false,
        visualizePitch: false,
      }),
      "bottom-right",
    );

    map.on("load", () => {
      map.addSource("trip-route", {
        type: "geojson",
        data: routeFeature(stops),
      });
      map.addLayer({
        id: "trip-route-line",
        type: "line",
        source: "trip-route",
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          "line-color": "#4f6547",
          "line-width": compact ? 3 : 3.4,
          "line-opacity": 0.92,
        },
      });
      setReady(true);
    });

    map.on("error", (event) => {
      if (event?.error) {
        setFailed(true);
      }
    });

    mapRef.current = map;

    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const source = map.getSource("trip-route");
    if (source) {
      source.setData(routeFeature(stops));
    }

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = stops.map((stop, index) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = "map-marker";
      element.classList.toggle("is-selected", stop.id === selectedStopId);
      element.textContent = String(index + 1);
      element.setAttribute("aria-label", `Select ${stop.title}`);
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        onSelectStop(stop.id);
      });

      return new Marker({ element, anchor: "center" })
        .setLngLat(stop.coords)
        .addTo(map);
    });

    const bounds = stops.reduce(
      (acc, stop) => acc.extend(stop.coords),
      new LngLatBounds(stops[0].coords, stops[0].coords),
    );

    map.fitBounds(bounds, {
      padding: compact
        ? { top: 50, right: 40, bottom: 50, left: 40 }
        : { top: 90, right: 70, bottom: 90, left: 70 },
      maxZoom: compact ? 12.6 : 13,
      duration: 800,
    });
  }, [compact, onSelectStop, ready, selectedStopId, stops]);

  return (
    <div className="map-canvas" aria-label="Interactive day route map">
      <div ref={containerRef} className="map-canvas__surface" />
      <div className="map-canvas__wash" aria-hidden="true" />
      {!ready && !failed ? (
        <div className="map-canvas__status">Loading route map</div>
      ) : null}
      {failed ? (
        <div className="map-canvas__status">
          Map unavailable. Route data remains accessible in the itinerary.
        </div>
      ) : null}
    </div>
  );
}
