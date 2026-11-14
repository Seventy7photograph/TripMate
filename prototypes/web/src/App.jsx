import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Calendar,
  Check,
  ChevronDown,
  Clock,
  GripVertical,
  Map,
  Mic,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
  Wallet,
} from "lucide-react";
import {
  budgetCategories,
  days,
  navItems,
  preferenceGroups,
  trip,
} from "./data";
import { MapCanvas } from "./MapCanvas";

const navIcons = {
  trips: Calendar,
  map: Map,
  budget: Wallet,
  preferences: Settings,
};

const navTitles = {
  trips: "Chongqing",
  map: "Route overview",
  budget: "Budget",
  preferences: "Travel profile",
};

function Sidebar({ activeNav, onNavigate }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="wordmark">TripMate</div>
      <nav className="sidebar__nav">
        {navItems.map((item) => {
          const Icon = navIcons[item.id];
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${activeNav === item.id ? "is-active" : ""}`}
              onClick={() => onNavigate(item.id)}
              aria-current={activeNav === item.id ? "page" : undefined}
            >
              <Icon size={18} strokeWidth={1.7} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <button
        type="button"
        className="sidebar__profile"
        onClick={() => onNavigate("preferences")}
        aria-label="Open travel profile"
      >
        <span className="profile-avatar">LK</span>
        <span className="profile-meta">
          <strong>Lukas</strong>
          <small>Travel profile</small>
        </span>
        <Settings size={16} strokeWidth={1.7} />
      </button>
    </aside>
  );
}

function MobileNav({ activeNav, onNavigate }) {
  return (
    <nav className="bottom-nav" aria-label="Mobile navigation">
      {navItems.map((item) => {
        const Icon = navIcons[item.id];
        return (
          <button
            key={item.id}
            type="button"
            className={activeNav === item.id ? "is-active" : ""}
            onClick={() => onNavigate(item.id)}
            aria-current={activeNav === item.id ? "page" : undefined}
          >
            <Icon size={20} strokeWidth={1.8} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function Topbar({ activeNav }) {
  return (
    <header className="topbar">
      <div className="topbar__mobile-brand">TripMate</div>
      <button type="button" className="trip-switcher">
        <span>{navTitles[activeNav]}</span>
        <span className="trip-switcher__dates">
          {activeNav === "trips" ? `${trip.dateRange}` : "Current trip"}
        </span>
        <ChevronDown size={15} strokeWidth={1.7} />
      </button>
      <div className="sync-status">
        <span className="sync-dot" />
        Synced just now
      </div>
    </header>
  );
}

function DayTabs({ activeDayId, onSelectDay, compact = false }) {
  return (
    <div className={`day-tabs ${compact ? "day-tabs--compact" : ""}`}>
      {days.map((day) => (
        <button
          key={day.id}
          type="button"
          className={activeDayId === day.id ? "is-active" : ""}
          onClick={() => onSelectDay(day.id)}
        >
          <strong>{day.label}</strong>
          <span>{day.date}</span>
        </button>
      ))}
    </div>
  );
}

function StopRow({ stop, index, isSelected, onSelect }) {
  return (
    <button
      type="button"
      className={`stop-row ${isSelected ? "is-selected" : ""}`}
      onClick={() => onSelect(stop.id)}
    >
      <span className="stop-row__rail" aria-hidden="true">
        <span className="stop-number">{index + 1}</span>
      </span>
      <span className="stop-row__main">
        <span className="stop-row__time">
          {stop.time} - {stop.endTime}
        </span>
        <strong>{stop.title}</strong>
        <span className="stop-row__area">{stop.area}</span>
        <span className="stop-row__note">{stop.note}</span>
      </span>
      <span className="stop-row__transit">{stop.transit}</span>
      <GripVertical className="stop-row__grip" size={16} strokeWidth={1.5} />
    </button>
  );
}

function AssistantComposer({
  value,
  onChange,
  onSubmit,
  assistantState,
  onApply,
  onDismiss,
}) {
  const isLoading = assistantState === "loading";
  const isReady = assistantState === "ready";

  return (
    <div className="assistant">
      {isReady ? (
        <div className="assistant-card" role="status">
          <div className="assistant-card__icon">
            <Sparkles size={17} />
          </div>
          <div>
            <strong>Lighter Day 2 draft</strong>
            <p>
              Remove Testbed 2, keep the late-afternoon river walk, and save
              about 1h 20m.
            </p>
          </div>
          <div className="assistant-card__actions">
            <button type="button" className="text-button" onClick={onDismiss}>
              Dismiss
            </button>
            <button type="button" className="primary-button" onClick={onApply}>
              <Check size={15} />
              Apply
            </button>
          </div>
        </div>
      ) : null}
      <form className="composer" onSubmit={onSubmit}>
        <Sparkles size={18} strokeWidth={1.8} />
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-label="Ask TripMate to refine this day"
          placeholder={
            isLoading
              ? "Drafting a lighter plan..."
              : "Ask TripMate to refine this day"
          }
          disabled={isLoading}
        />
        <button type="button" className="icon-button" aria-label="Use voice">
          <Mic size={17} strokeWidth={1.8} />
        </button>
        <button
          type="submit"
          className="send-button"
          aria-label="Send request"
          disabled={isLoading || !value.trim()}
        >
          <Send size={16} strokeWidth={1.8} />
        </button>
      </form>
    </div>
  );
}

function TripWorkspace({
  activeDayId,
  onSelectDay,
  activeDay,
  selectedStopId,
  onSelectStop,
  estimatedBudget,
  composerValue,
  onComposerChange,
  onSubmitPrompt,
  assistantState,
  onApplyDraft,
  onDismissDraft,
}) {
  return (
    <div className="workspace">
      <section className="trip-heading">
        <div>
          <p className="eyebrow">Travel plan</p>
          <h1>Chongqing</h1>
          <p className="trip-meta">
            {trip.dateRange} <span>/</span> {trip.travelers} travelers
          </p>
        </div>
        <div className="budget-glance">
          <span>Budget {trip.currency} {trip.budgetTotal.toLocaleString()}</span>
          <span className="budget-glance__divider" />
          <span>Estimated {trip.currency} {estimatedBudget.toLocaleString()}</span>
        </div>
      </section>

      <div className="planner-layout">
        <section className="itinerary-panel" aria-label="Daily itinerary">
          <DayTabs activeDayId={activeDayId} onSelectDay={onSelectDay} />
          <div className="day-summary">
            <span>{activeDay.stops[0]?.time} - {activeDay.stops.at(-1)?.endTime}</span>
            <span>{activeDay.stops.length} stops</span>
          </div>
          <div className="stop-list">
            {activeDay.stops.map((stop, index) => (
              <StopRow
                key={stop.id}
                stop={stop}
                index={index}
                isSelected={stop.id === selectedStopId}
                onSelect={onSelectStop}
              />
            ))}
          </div>
          <div className="day-footer">
            <button type="button" className="quiet-action">
              <Plus size={16} />
              Add a stop
            </button>
            <button type="button" className="quiet-action">
              <Search size={16} />
              Search nearby
            </button>
          </div>
        </section>

        <section className="map-panel" aria-label="Day route">
          <MapCanvas
            stops={activeDay.stops}
            selectedStopId={selectedStopId}
            onSelectStop={onSelectStop}
          />
          <div className="map-meta">
            <span>{activeDay.theme}</span>
            <span>{activeDay.stops.length} stops</span>
          </div>
          <div className="map-weather">
            <Clock size={15} />
            18 C / Light rain after 16:00
          </div>
          <AssistantComposer
            value={composerValue}
            onChange={onComposerChange}
            onSubmit={onSubmitPrompt}
            assistantState={assistantState}
            onApply={onApplyDraft}
            onDismiss={onDismissDraft}
          />
        </section>
      </div>
    </div>
  );
}

function MapScreen({
  activeDayId,
  onSelectDay,
  activeDay,
  selectedStopId,
  onSelectStop,
}) {
  return (
    <div className="workspace workspace--map">
      <section className="view-heading">
        <div>
          <p className="eyebrow">Route overview</p>
          <h1>Move through the city</h1>
          <p className="trip-meta">
            Real route structure, transit time, and source-aware stops.
          </p>
        </div>
        <div className="map-status">
          <span className="sync-dot" />
          Route verified
        </div>
      </section>
      <DayTabs activeDayId={activeDayId} onSelectDay={onSelectDay} compact />
      <div className="map-screen">
        <div className="map-screen__canvas">
          <MapCanvas
            stops={activeDay.stops}
            selectedStopId={selectedStopId}
            onSelectStop={onSelectStop}
            compact
          />
        </div>
        <aside className="map-screen__rail" aria-label="Route stops">
          {activeDay.stops.map((stop, index) => (
            <button
              type="button"
              key={stop.id}
              className={`map-rail-stop ${selectedStopId === stop.id ? "is-active" : ""}`}
              onClick={() => onSelectStop(stop.id)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{stop.title}</strong>
                <small>{stop.transit}</small>
              </span>
              <ArrowRight size={16} />
            </button>
          ))}
        </aside>
      </div>
    </div>
  );
}

function BudgetScreen({ estimatedBudget }) {
  const remaining = trip.budgetTotal - estimatedBudget;
  return (
    <div className="workspace workspace--budget">
      <section className="view-heading">
        <div>
          <p className="eyebrow">Travel budget</p>
          <h1>Quietly in control</h1>
          <p className="trip-meta">
            Estimated spend updates as your itinerary changes.
          </p>
        </div>
        <div className="budget-pill">
          <span>Remaining</span>
          <strong>{trip.currency} {remaining.toLocaleString()}</strong>
        </div>
      </section>
      <section className="budget-sheet">
        <div className="budget-sheet__header">
          <div>
            <span>Estimated total</span>
            <strong>{trip.currency} {estimatedBudget.toLocaleString()}</strong>
          </div>
          <div>
            <span>Budget</span>
            <strong>{trip.currency} {trip.budgetTotal.toLocaleString()}</strong>
          </div>
          <div>
            <span>Per traveler</span>
            <strong>{trip.currency} {Math.round(estimatedBudget / trip.travelers).toLocaleString()}</strong>
          </div>
        </div>
        <div className="budget-rows">
          {budgetCategories.map((category) => (
            <div className="budget-row" key={category.label}>
              <div className="budget-row__label">
                <span>{category.label}</span>
                <strong>{trip.currency} {category.spent.toLocaleString()}</strong>
              </div>
              <div className="budget-bar">
                <span
                  className={`budget-bar__fill budget-bar__fill--${category.color}`}
                  style={{ width: `${Math.min(100, (category.spent / category.planned) * 100)}%` }}
                />
              </div>
              <span className="budget-row__plan">
                of {trip.currency} {category.planned.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
        <div className="budget-note">
          <Sparkles size={18} />
          <p>
            Removing one paid stop on Day 2 keeps the plan under budget and
            preserves the evening river walk.
          </p>
          <button type="button" className="quiet-action">
            Review suggestion
          </button>
        </div>
      </section>
    </div>
  );
}

function PreferenceChips({ values, selected, onToggle }) {
  return (
    <div className="chip-row">
      {values.map((value) => (
        <button
          type="button"
          key={value}
          className={selected.includes(value) ? "is-selected" : ""}
          onClick={() => onToggle(value)}
        >
          {selected.includes(value) ? <Check size={14} /> : null}
          {value}
        </button>
      ))}
    </div>
  );
}

function PreferencesScreen({
  preferences,
  onSetPace,
  onTogglePreference,
}) {
  return (
    <div className="workspace workspace--preferences">
      <section className="view-heading">
        <div>
          <p className="eyebrow">Travel profile</p>
          <h1>Plan the way you travel</h1>
          <p className="trip-meta">
            Explicit preferences guide the planner without locking it down.
          </p>
        </div>
        <div className="map-status">
          <Check size={15} />
          Preferences saved
        </div>
      </section>
      <section className="preference-sheet">
        <div className="preference-section">
          <div className="preference-copy">
            <span className="section-number">01</span>
            <div>
              <h2>Daily pace</h2>
              <p>Choose the default energy level for new days.</p>
            </div>
          </div>
          <div className="segmented-control">
            {preferenceGroups.pace.map((pace) => (
              <button
                key={pace}
                type="button"
                className={preferences.pace === pace ? "is-active" : ""}
                onClick={() => onSetPace(pace)}
              >
                {pace}
              </button>
            ))}
          </div>
        </div>
        <div className="preference-section">
          <div className="preference-copy">
            <span className="section-number">02</span>
            <div>
              <h2>What you enjoy</h2>
              <p>These choices influence stop suggestions and route rhythm.</p>
            </div>
          </div>
          <PreferenceChips
            values={preferenceGroups.interests}
            selected={preferences.interests}
            onToggle={(value) => onTogglePreference("interests", value)}
          />
        </div>
        <div className="preference-section">
          <div className="preference-copy">
            <span className="section-number">03</span>
            <div>
              <h2>Preferred transport</h2>
              <p>Routes will favor these modes while keeping transit realistic.</p>
            </div>
          </div>
          <PreferenceChips
            values={preferenceGroups.transport}
            selected={preferences.transport}
            onToggle={(value) => onTogglePreference("transport", value)}
          />
        </div>
        <div className="preference-section preference-section--memory">
          <div className="preference-copy">
            <span className="section-number">04</span>
            <div>
              <h2>Remember my choices</h2>
              <p>
                Optional long-term memory can be reviewed and deleted at any
                time.
              </p>
            </div>
          </div>
          <button
            type="button"
            className={`toggle ${preferences.memory ? "is-on" : ""}`}
            onClick={() => onTogglePreference("memory", !preferences.memory)}
            aria-pressed={preferences.memory}
          >
            <span />
          </button>
        </div>
      </section>
    </div>
  );
}

export function App() {
  const [activeNav, setActiveNav] = useState("trips");
  const [activeDayId, setActiveDayId] = useState("day-2");
  const [tripDays, setTripDays] = useState(days);
  const [selectedStopId, setSelectedStopId] = useState("d2-1");
  const [estimatedBudget, setEstimatedBudget] = useState(2180);
  const [composerValue, setComposerValue] = useState("");
  const [assistantState, setAssistantState] = useState("idle");
  const [toast, setToast] = useState("");
  const [preferences, setPreferences] = useState({
    pace: "Balanced",
    interests: ["Food", "Photography"],
    transport: ["Metro", "Walking"],
    memory: true,
  });
  const timerRef = useRef(null);

  const activeDay =
    tripDays.find((day) => day.id === activeDayId) ?? tripDays[1];

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  function navigate(nextNav) {
    setActiveNav(nextNav);
    if (nextNav === "trips" || nextNav === "map") {
      setSelectedStopId(activeDay.stops[0]?.id ?? "");
    }
  }

  function selectDay(dayId) {
    const nextDay = tripDays.find((day) => day.id === dayId);
    setActiveDayId(dayId);
    setSelectedStopId(nextDay?.stops[0]?.id ?? "");
  }

  function selectStop(stopId) {
    setSelectedStopId(stopId);
  }

  function submitPrompt(event) {
    event.preventDefault();
    if (!composerValue.trim() || assistantState === "loading") return;
    setAssistantState("loading");
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      setAssistantState("ready");
    }, 900);
  }

  function applyDraft() {
    setTripDays((currentDays) =>
      currentDays.map((day) =>
        day.id === "day-2"
          ? {
              ...day,
              stops: day.stops.filter((stop) => stop.id !== "d2-3"),
            }
          : day,
      ),
    );
    setEstimatedBudget((value) => Math.max(0, value - 96));
    setAssistantState("idle");
    setComposerValue("");
    setToast("Day 2 updated. Route and budget recalculated.");
  }

  function togglePreference(key, value) {
    if (key === "memory") {
      setPreferences((current) => ({ ...current, memory: value }));
      return;
    }
    setPreferences((current) => {
      const existing = current[key];
      return {
        ...current,
        [key]: existing.includes(value)
          ? existing.filter((item) => item !== value)
          : [...existing, value],
      };
    });
  }

  return (
    <div className="app-shell">
      <Sidebar activeNav={activeNav} onNavigate={navigate} />
      <div className="app-main">
        <Topbar activeNav={activeNav} />
        {activeNav === "trips" ? (
          <TripWorkspace
            activeDayId={activeDayId}
            onSelectDay={selectDay}
            activeDay={activeDay}
            selectedStopId={selectedStopId}
            onSelectStop={selectStop}
            estimatedBudget={estimatedBudget}
            composerValue={composerValue}
            onComposerChange={setComposerValue}
            onSubmitPrompt={submitPrompt}
            assistantState={assistantState}
            onApplyDraft={applyDraft}
            onDismissDraft={() => setAssistantState("idle")}
          />
        ) : null}
        {activeNav === "map" ? (
          <MapScreen
            activeDayId={activeDayId}
            onSelectDay={selectDay}
            activeDay={activeDay}
            selectedStopId={selectedStopId}
            onSelectStop={selectStop}
          />
        ) : null}
        {activeNav === "budget" ? (
          <BudgetScreen estimatedBudget={estimatedBudget} />
        ) : null}
        {activeNav === "preferences" ? (
          <PreferencesScreen
            preferences={preferences}
            onSetPace={(pace) =>
              setPreferences((current) => ({ ...current, pace }))
            }
            onTogglePreference={togglePreference}
          />
        ) : null}
      </div>
      <MobileNav activeNav={activeNav} onNavigate={navigate} />
      {toast ? (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      ) : null}
    </div>
  );
}
