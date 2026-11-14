import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Check,
  ChevronDown,
  Map,
  Mic,
  Route,
  Send,
  Settings2,
  Sparkles,
  Wallet,
} from "lucide-react";
import {
  BottomSheet,
  Carousel,
  KeyboardTextarea,
  MobileScroll,
  useKeyboard,
} from "./mobile";
import { DayMap, type MapStop } from "./MapCanvas";

type Stop = MapStop & {
  time: string;
  endTime: string;
  area: string;
  transit: string;
  note: string;
  cost: number;
};

type Day = {
  id: string;
  label: string;
  date: string;
  theme: string;
  stops: Stop[];
};

const DAYS: Day[] = [
  {
    id: "day-1",
    label: "Day 1",
    date: "Nov 14",
    theme: "Arrival & river edge",
    stops: [
      {
        id: "d1-1",
        time: "14:00",
        endTime: "15:00",
        title: "Hotel check-in",
        area: "Jiefangbei",
        transit: "From Chongqing North",
        note: "Settle in and take a slow first walk.",
        cost: 0,
        coords: [106.5771, 29.5581],
      },
      {
        id: "d1-2",
        time: "16:00",
        endTime: "17:30",
        title: "Raffles City",
        area: "Chaotianmen",
        transit: "12 min · Metro",
        note: "Sky terrace and river convergence views.",
        cost: 0,
        coords: [106.587, 29.565],
      },
      {
        id: "d1-3",
        time: "19:00",
        endTime: "20:30",
        title: "Hongyadong",
        area: "Yuzhong District",
        transit: "18 min · Taxi",
        note: "Golden-hour riverside walk and dinner nearby.",
        cost: 120,
        coords: [106.5795, 29.5638],
      },
    ],
  },
  {
    id: "day-2",
    label: "Day 2",
    date: "Nov 15",
    theme: "Hillside rhythm",
    stops: [
      {
        id: "d2-1",
        time: "09:00",
        endTime: "11:00",
        title: "Liziba",
        area: "Yuzhong District",
        transit: "12 min · Metro Line 2",
        note: "Watch the monorail pass through the building.",
        cost: 28,
        coords: [106.5119, 29.5525],
      },
      {
        id: "d2-2",
        time: "11:20",
        endTime: "13:00",
        title: "Eling Park",
        area: "Yuzhong District",
        transit: "18 min · Taxi / Didi",
        note: "Hillside pavilions, tree cover, and skyline views.",
        cost: 30,
        coords: [106.523, 29.554],
      },
      {
        id: "d2-3",
        time: "14:00",
        endTime: "16:00",
        title: "Testbed 2",
        area: "Nan'an District",
        transit: "14 min · Metro Line 1",
        note: "Creative riverside district for coffee and a slower pause.",
        cost: 96,
        coords: [106.551, 29.557],
      },
      {
        id: "d2-4",
        time: "16:30",
        endTime: "18:30",
        title: "Jiefangbei",
        area: "Yuzhong District",
        transit: "12 min · Walking",
        note: "Historic core, snack streets, and an evening city walk.",
        cost: 140,
        coords: [106.577, 29.558],
      },
      {
        id: "d2-5",
        time: "19:00",
        endTime: "20:30",
        title: "Hongyadong",
        area: "Yuzhong District",
        transit: "22 min · Taxi / Didi",
        note: "End with the illuminated stilted buildings and river view.",
        cost: 0,
        coords: [106.5795, 29.5638],
      },
    ],
  },
  {
    id: "day-3",
    label: "Day 3",
    date: "Nov 16",
    theme: "Old lanes, slow morning",
    stops: [
      {
        id: "d3-1",
        time: "09:30",
        endTime: "11:00",
        title: "Shancheng Trail",
        area: "Yuzhong District",
        transit: "From hotel · 10 min",
        note: "Quiet stairs and layered alleys before the city gets busy.",
        cost: 0,
        coords: [106.566, 29.559],
      },
      {
        id: "d3-2",
        time: "11:30",
        endTime: "13:00",
        title: "Testbed 2",
        area: "Nan'an District",
        transit: "16 min · Metro",
        note: "Late brunch and one last riverfront stop.",
        cost: 90,
        coords: [106.551, 29.557],
      },
      {
        id: "d3-3",
        time: "15:00",
        endTime: "16:00",
        title: "Departure",
        area: "Chongqing North",
        transit: "38 min · Metro",
        note: "Leave a comfortable buffer for the station.",
        cost: 24,
        coords: [106.5509, 29.6089],
      },
    ],
  },
];

const NAV_ITEMS = [
  { id: "trips", label: "Trips", Icon: CalendarDays },
  { id: "map", label: "Map", Icon: Map },
  { id: "budget", label: "Budget", Icon: Wallet },
  { id: "preferences", label: "Profile", Icon: Settings2 },
] as const;

const BUDGET = [
  { label: "Stay", value: 900, width: 100 },
  { label: "Transport", value: 580, width: 94 },
  { label: "Food", value: 420, width: 72 },
  { label: "Tickets", value: 180, width: 100 },
  { label: "Other", value: 100, width: 100 },
];

function Header() {
  return (
    <header className="app-header">
      <div className="brand-row">
        <span className="mobile-wordmark">TripMate</span>
        <span className="mobile-sync">
          <span />
          Synced
        </span>
        <button type="button" className="profile-button" aria-label="Open profile">
          LK
        </button>
      </div>
      <div className="trip-title-row">
        <div>
          <p className="mobile-eyebrow">Travel plan</p>
          <h1>Chongqing</h1>
          <p className="mobile-trip-meta">Nov 14 - 16, 2026 · 2 travelers</p>
        </div>
      </div>
    </header>
  );
}

function DayPicker({
  activeDayId,
  onSelect,
}: {
  activeDayId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <Carousel ariaLabel="Choose itinerary day" className="day-carousel">
      <div className="day-carousel-track">
        {DAYS.map((day) => (
          <button
            key={day.id}
            type="button"
            className={`mobile-day-pill ${activeDayId === day.id ? "is-active" : ""}`}
            onClick={() => onSelect(day.id)}
          >
            <strong>{day.label}</strong>
            <span>{day.date}</span>
          </button>
        ))}
      </div>
    </Carousel>
  );
}

function StopList({
  stops,
  selectedStopId,
  onSelect,
}: {
  stops: Stop[];
  selectedStopId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="mobile-stops" aria-label="Daily itinerary stops">
      {stops.map((stop, index) => (
        <button
          type="button"
          key={stop.id}
          className={`mobile-stop ${selectedStopId === stop.id ? "is-selected" : ""}`}
          onClick={() => onSelect(stop.id)}
        >
          <span className="mobile-stop-rail">
            <span>{index + 1}</span>
          </span>
          <span className="mobile-stop-copy">
            <span className="mobile-stop-time">
              {stop.time} - {stop.endTime}
            </span>
            <strong>{stop.title}</strong>
            <span className="mobile-stop-area">{stop.area}</span>
            <span className="mobile-stop-note">{stop.note}</span>
          </span>
          <span className="mobile-stop-transit">{stop.transit}</span>
        </button>
      ))}
    </section>
  );
}

function MapPreview({
  day,
  selectedStopId,
  onSelectStop,
}: {
  day: Day;
  selectedStopId: string;
  onSelectStop: (id: string) => void;
}) {
  return (
    <section className="map-preview-block">
      <div className="map-preview-copy">
        <span>{day.theme}</span>
        <span>{day.stops.length} stops</span>
      </div>
      <DayMap
        stops={day.stops}
        selectedStopId={selectedStopId}
        onSelectStop={onSelectStop}
        variant="preview"
      />
    </section>
  );
}

function TripsScreen({
  activeDay,
  activeDayId,
  onSelectDay,
  selectedStopId,
  onSelectStop,
  estimatedBudget,
  draftReady,
  onApplyDraft,
  onDismissDraft,
}: {
  activeDay: Day;
  activeDayId: string;
  onSelectDay: (id: string) => void;
  selectedStopId: string;
  onSelectStop: (id: string) => void;
  estimatedBudget: number;
  draftReady: boolean;
  onApplyDraft: () => void;
  onDismissDraft: () => void;
}) {
  return (
    <>
      <Header />
      <DayPicker activeDayId={activeDayId} onSelect={onSelectDay} />
      <section className="mobile-day-summary">
        <span>{activeDay.stops[0]?.time} - {activeDay.stops.at(-1)?.endTime}</span>
        <span>{activeDay.stops.length} stops</span>
      </section>
      <MapPreview
        day={activeDay}
        selectedStopId={selectedStopId}
        onSelectStop={onSelectStop}
      />
      {draftReady ? (
        <section className="mobile-draft-card">
          <div className="mobile-draft-icon">
            <Sparkles size={16} />
          </div>
          <div>
            <strong>Lighter Day 2 draft</strong>
            <p>Remove Testbed 2 and save about 1h 20m.</p>
          </div>
          <div className="mobile-draft-actions">
            <button type="button" className="mobile-text-button" onClick={onDismissDraft}>
              Dismiss
            </button>
            <button type="button" className="mobile-primary-button" onClick={onApplyDraft}>
              <Check size={14} />
              Apply
            </button>
          </div>
        </section>
      ) : null}
      <StopList
        stops={activeDay.stops}
        selectedStopId={selectedStopId}
        onSelect={onSelectStop}
      />
      <section className="mobile-budget-line">
        <Wallet size={15} />
        <span>CNY {estimatedBudget.toLocaleString()} est.</span>
        <span>/ CNY 3,000 total</span>
      </section>
    </>
  );
}

function MapScreen({
  activeDay,
  activeDayId,
  onSelectDay,
  selectedStopId,
  onSelectStop,
}: {
  activeDay: Day;
  activeDayId: string;
  onSelectDay: (id: string) => void;
  selectedStopId: string;
  onSelectStop: (id: string) => void;
}) {
  return (
    <>
      <Header />
      <DayPicker activeDayId={activeDayId} onSelect={onSelectDay} />
      <section className="mobile-map-screen">
        <div className="mobile-map-screen-copy">
          <p className="mobile-eyebrow">Route overview</p>
          <h2>{activeDay.theme}</h2>
          <span>
            <Route size={14} />
            Verified route · {activeDay.stops.length} stops
          </span>
        </div>
        <DayMap
          stops={activeDay.stops}
          selectedStopId={selectedStopId}
          onSelectStop={onSelectStop}
          variant="full"
        />
        <div className="mobile-route-list">
          {activeDay.stops.map((stop, index) => (
            <button
              type="button"
              key={stop.id}
              className={selectedStopId === stop.id ? "is-active" : ""}
              onClick={() => onSelectStop(stop.id)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{stop.title}</strong>
                <small>{stop.transit}</small>
              </span>
              <ChevronDown size={15} />
            </button>
          ))}
        </div>
      </section>
    </>
  );
}

function BudgetScreen({ estimatedBudget }: { estimatedBudget: number }) {
  return (
    <>
      <Header />
      <section className="mobile-view-title">
        <p className="mobile-eyebrow">Travel budget</p>
        <h2>Quietly in control</h2>
        <p>Estimated spend updates as the itinerary changes.</p>
      </section>
      <section className="mobile-budget-summary">
        <span>Remaining</span>
        <strong>CNY {(3000 - estimatedBudget).toLocaleString()}</strong>
        <small>of CNY 3,000</small>
      </section>
      <section className="mobile-budget-list">
        {BUDGET.map((item) => (
          <div key={item.label}>
            <div className="mobile-budget-row-title">
              <span>{item.label}</span>
              <strong>CNY {item.value.toLocaleString()}</strong>
            </div>
            <div className="mobile-budget-bar">
              <span style={{ width: `${item.width}%` }} />
            </div>
          </div>
        ))}
      </section>
      <section className="mobile-budget-note">
        <Sparkles size={18} />
        <p>Removing one Day 2 stop keeps this trip comfortably under budget.</p>
      </section>
    </>
  );
}

function PreferencesScreen() {
  const [pace, setPace] = useState("Balanced");
  const [selected, setSelected] = useState(["Food", "Photography"]);
  const [memory, setMemory] = useState(true);

  const toggle = (value: string) => {
    setSelected((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  };

  return (
    <>
      <Header />
      <section className="mobile-view-title">
        <p className="mobile-eyebrow">Travel profile</p>
        <h2>Plan your way</h2>
        <p>Preferences guide the planner without locking it down.</p>
      </section>
      <section className="mobile-preferences">
        <div className="mobile-preference-section">
          <span className="mobile-section-number">01</span>
          <div>
            <h3>Daily pace</h3>
            <p>Default energy level for new days.</p>
          </div>
          <div className="mobile-segmented">
            {["Relaxed", "Balanced", "Intensive"].map((option) => (
              <button
                type="button"
                key={option}
                className={pace === option ? "is-active" : ""}
                onClick={() => setPace(option)}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
        <div className="mobile-preference-section">
          <span className="mobile-section-number">02</span>
          <div>
            <h3>What you enjoy</h3>
            <p>Used for stop suggestions and route rhythm.</p>
          </div>
          <div className="mobile-chip-row">
            {["Food", "Photography", "Nature", "Architecture", "Local culture"].map(
              (option) => (
                <button
                  type="button"
                  key={option}
                  className={selected.includes(option) ? "is-active" : ""}
                  onClick={() => toggle(option)}
                >
                  {selected.includes(option) ? <Check size={13} /> : null}
                  {option}
                </button>
              ),
            )}
          </div>
        </div>
        <div className="mobile-preference-section">
          <span className="mobile-section-number">03</span>
          <div>
            <h3>Remember choices</h3>
            <p>Long-term memory can be reviewed and deleted.</p>
          </div>
          <button
            type="button"
            className={`mobile-toggle ${memory ? "is-on" : ""}`}
            onClick={() => setMemory((value) => !value)}
            aria-pressed={memory}
          >
            <span />
          </button>
        </div>
      </section>
    </>
  );
}

function BottomNav({
  activeTab,
  onChange,
}: {
  activeTab: string;
  onChange: (tab: string) => void;
}) {
  return (
    <nav className="mobile-tabbar" aria-label="Main navigation">
      {NAV_ITEMS.map(({ id, label, Icon }) => (
        <button
          type="button"
          key={id}
          className={activeTab === id ? "is-active" : ""}
          onClick={() => onChange(id)}
          aria-current={activeTab === id ? "page" : undefined}
        >
          <Icon size={19} strokeWidth={1.8} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

export default function Prototype() {
  const [activeTab, setActiveTab] = useState("trips");
  const [activeDayId, setActiveDayId] = useState("day-2");
  const [tripDays, setTripDays] = useState(DAYS);
  const [selectedStopId, setSelectedStopId] = useState("d2-1");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantText, setAssistantText] = useState("");
  const [draftReady, setDraftReady] = useState(false);
  const [estimatedBudget, setEstimatedBudget] = useState(2180);
  const [toast, setToast] = useState("");
  const keyboard = useKeyboard();

  const activeDay = useMemo(
    () => tripDays.find((day) => day.id === activeDayId) ?? tripDays[1],
    [activeDayId, tripDays],
  );

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(() => setToast(""), 2400);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const selectDay = (dayId: string) => {
    const nextDay = tripDays.find((day) => day.id === dayId);
    setActiveDayId(dayId);
    setSelectedStopId(nextDay?.stops[0]?.id ?? "");
  };

  const sendAssistant = () => {
    keyboard.hide();
    setAssistantOpen(false);
    setAssistantText("");
    setDraftReady(true);
    setActiveTab("trips");
  };

  const applyDraft = () => {
    setTripDays((current) =>
      current.map((day) =>
        day.id === "day-2"
          ? { ...day, stops: day.stops.filter((stop) => stop.id !== "d2-3") }
          : day,
      ),
    );
    setEstimatedBudget((value) => value - 96);
    setDraftReady(false);
    setToast("Day 2 updated");
  };

  return (
    <>
      <MobileScroll className="app-screen">
        <main className={`mobile-app-content mobile-app-content--${activeTab}`}>
          {activeTab === "trips" ? (
            <TripsScreen
              activeDay={activeDay}
              activeDayId={activeDayId}
              onSelectDay={selectDay}
              selectedStopId={selectedStopId}
              onSelectStop={setSelectedStopId}
              estimatedBudget={estimatedBudget}
              draftReady={draftReady}
              onApplyDraft={applyDraft}
              onDismissDraft={() => setDraftReady(false)}
            />
          ) : null}
          {activeTab === "map" ? (
            <MapScreen
              activeDay={activeDay}
              activeDayId={activeDayId}
              onSelectDay={selectDay}
              selectedStopId={selectedStopId}
              onSelectStop={setSelectedStopId}
            />
          ) : null}
          {activeTab === "budget" ? (
            <BudgetScreen estimatedBudget={estimatedBudget} />
          ) : null}
          {activeTab === "preferences" ? <PreferencesScreen /> : null}
        </main>
      </MobileScroll>
      <BottomNav activeTab={activeTab} onChange={setActiveTab} />
      {activeTab === "trips" ? (
        <button
          type="button"
          className="mobile-composer"
          onClick={() => setAssistantOpen(true)}
        >
          <Sparkles size={17} />
          <span>Ask TripMate to refine this day</span>
          <Mic size={16} />
          <Send size={15} />
        </button>
      ) : null}
      <BottomSheet
        open={assistantOpen}
        onOpenChange={setAssistantOpen}
        title="Refine Day 2"
        description="Tell TripMate what to change. Nothing is applied until you confirm the draft."
        snap={0.74}
      >
        <div className="mobile-assistant-sheet">
          <KeyboardTextarea
            value={assistantText}
            onChange={(event) => setAssistantText(event.target.value)}
            placeholder="Make Day 2 lighter and keep the evening river walk"
            aria-label="Describe itinerary change"
          />
          <div className="mobile-quick-prompts">
            {["Make it lighter", "Move lunch later", "Add a photo stop"].map(
              (prompt) => (
                <button
                  type="button"
                  key={prompt}
                  onClick={() => setAssistantText(prompt)}
                >
                  {prompt}
                </button>
              ),
            )}
          </div>
          <button
            type="button"
            className="mobile-sheet-submit"
            disabled={!assistantText.trim()}
            onClick={sendAssistant}
          >
            <Sparkles size={16} />
            Draft the change
          </button>
        </div>
      </BottomSheet>
      {toast ? (
        <div className="mobile-toast" role="status">
          <Check size={15} />
          {toast}
        </div>
      ) : null}
    </>
  );
}
