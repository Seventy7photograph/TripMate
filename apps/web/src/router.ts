// 文件说明：Web 前端模块：router。
import { createRouter, createWebHistory } from "vue-router";

import AuthView from "./features/auth/AuthView.vue";
import ProfileView from "./features/auth/ProfileView.vue";
import MemoryView from "./pages/settings/MemoryView.vue";
import FavoritesView from "./pages/favorites/FavoritesView.vue";
import HomeView from "./pages/HomeView.vue";
import TripItineraryView from "./pages/itinerary/TripItineraryView.vue";
import PlacesView from "./pages/places/PlacesView.vue";
import BudgetView from "./pages/budget/BudgetView.vue";
import PlanningView from "./pages/planning/PlanningView.vue";
import TripMapView from "./pages/trips/detail/map.vue";
import ShareView from "./pages/share/ShareView.vue";
import TripCreateView from "./pages/trips/TripCreateView.vue";
import TripDetailView from "./pages/trips/TripDetailView.vue";
import TripsView from "./pages/trips/TripsView.vue";
import { useAuthStore } from "./stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to) {
    if (to.hash) {
      return { el: to.hash, behavior: "smooth" };
    }
    return { top: 0 };
  },
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView,
      meta: { public: true },
    },
    {
      path: "/profile",
      name: "profile",
      component: ProfileView,
      meta: { requiresAuth: true },
    },
    {
      path: "/settings/memory",
      name: "memory-settings",
      component: MemoryView,
      meta: { requiresAuth: true },
    },
    {
      path: "/places",
      name: "places",
      component: PlacesView,
      meta: { requiresAuth: true },
    },
    {
      path: "/trips",
      name: "trips",
      component: TripsView,
      meta: { requiresAuth: true },
    },
    {
      path: "/favorites",
      name: "favorites",
      component: FavoritesView,
      meta: { requiresAuth: true },
    },
    {
      path: "/assistant",
      redirect: { name: "home" },
    },
    {
      path: "/trips/new",
      name: "trip-create",
      component: TripCreateView,
      meta: { requiresAuth: true },
    },
    {
      path: "/trips/:tripId/plan",
      name: "trip-plan",
      component: PlanningView,
      meta: { requiresAuth: true },
    },
    {
      path: "/trips/:tripId/budget",
      name: "trip-budget",
      component: BudgetView,
      meta: { requiresAuth: true },
    },
    {
      path: "/trips/:tripId/map",
      name: "trip-map",
      component: TripMapView,
      meta: { requiresAuth: true },
    },
    {
      path: "/trips/:tripId/days/:dayId/map",
      name: "trip-day-map",
      component: TripMapView,
      meta: { requiresAuth: true },
    },
    {
      path: "/trips/:tripId/itinerary",
      name: "trip-itinerary",
      component: TripItineraryView,
      meta: { requiresAuth: true },
    },
    {
      path: "/trips/:tripId",
      name: "trip-detail",
      component: TripDetailView,
      meta: { requiresAuth: true },
    },
    {
      path: "/login",
      name: "login",
      component: AuthView,
      props: { mode: "login" },
      meta: { guestOnly: true },
    },
    {
      path: "/share/:token",
      name: "shared-trip",
      component: ShareView,
      meta: { publicLayout: true },
    },
    {
      path: "/register",
      name: "register",
      component: AuthView,
      props: { mode: "register" },
      meta: { guestOnly: true },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  await auth.initialize();

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return {
      name: "login",
      query: { redirect: to.fullPath },
    };
  }

  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: "home" };
  }

  return true;
});
