import { useEffect, useRef, useState } from "react";
import {
  type GeoJSONSource,
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export type MapStop = {
  id: string;
  title: string;
  coords: [number, number];
};

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

function routeFeature(stops: MapStop[]) {
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "LineString" as const,
      coordinates: stops.map((stop) => stop.coords),
    },
  };
}

export function DayMap({
  stops,
  selectedStopId,
  onSelectStop,
  variant = "preview",
}: {
  stops: MapStop[];
  selectedStopId: string;
  onSelectStop: (id: string) => void;
  variant?: "preview" | "full";
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [106.555, 29.558],
      zoom: 12.1,
      attributionControl: false,
      dragRotate: false,
      touchPitch: false,
    });

    map.on("load", () => {
      map.addSource("mobile-trip-route", {
        type: "geojson",
        data: routeFeature(stops),
      });
      map.addLayer({
        id: "mobile-trip-route-line",
        type: "line",
        source: "mobile-trip-route",
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          "line-color": "#4f6547",
          "line-width": variant === "full" ? 3.3 : 2.8,
          "line-opacity": 0.92,
        },
      });
      setReady(true);
    });

    map.on("error", (event) => {
      if (event?.error) setFailed(true);
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

    const source = map.getSource("mobile-trip-route") as GeoJSONSource | undefined;
    source?.setData(routeFeature(stops));

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = stops.map((stop, index) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = "mobile-map-marker";
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
      padding: variant === "full" ? 54 : 34,
      maxZoom: variant === "full" ? 13 : 12.5,
      duration: 720,
    });
  }, [onSelectStop, ready, selectedStopId, stops, variant]);

  return (
    <div
      className={`mobile-map mobile-map--${variant}`}
      data-scroll-drag="ignore"
      aria-label="Interactive day route map"
    >
      <div ref={containerRef} className="mobile-map__surface" />
      {!ready && !failed ? (
        <span className="mobile-map__status">Loading route</span>
      ) : null}
      {failed ? (
        <span className="mobile-map__status">Map unavailable</span>
      ) : null}
    </div>
  );
}
