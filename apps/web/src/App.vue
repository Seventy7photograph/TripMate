<!-- 文件说明：Web 前端模块：App。 -->
<script setup lang="ts">
import { Heart, Menu, UserRound, X } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";

import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const route = useRoute();
const mobileMenuOpen = ref(false);

const isAuthRoute = computed(
  () => Boolean(route.meta.guestOnly) || Boolean(route.meta.publicLayout),
);
const isPublicHome = computed(() => isHome.value && !auth.isAuthenticated);
const isHome = computed(() => route.name === "home");
const isMap = computed(
  () => route.name === "trip-map" || route.name === "trip-day-map",
);
const isTrips = computed(
  () => route.path === "/trips" || route.path.startsWith("/trips/"),
);
const isPlaces = computed(() => route.path.startsWith("/places"));
const isFavorites = computed(() => route.path.startsWith("/favorites"));
const isProfile = computed(() => route.name === "profile");
const shellClass = computed(() => ({
  "app-shell--home": isHome.value,
  "app-shell--map": isMap.value,
  "app-shell--standard": !isHome.value && !isMap.value,
}));

watch(
  () => route.fullPath,
  () => {
    mobileMenuOpen.value = false;
  },
);

function navClass(active: boolean): Record<string, boolean> {
  return { "is-active": active };
}
</script>

<template>
  <div v-if="isAuthRoute" class="guest-shell guest-shell--auth">
    <RouterView />
  </div>

  <div v-else class="app-shell" :class="shellClass">
    <header class="app-topbar">
      <RouterLink class="app-brand" to="/" aria-label="TripMate 首页">
        TripMate
      </RouterLink>

      <nav class="app-nav" aria-label="主导航">
        <RouterLink :class="navClass(isHome)" to="/">对话</RouterLink>
        <RouterLink :class="navClass(isTrips)" to="/trips">行程</RouterLink>
        <RouterLink :class="navClass(isPlaces)" to="/places">探索</RouterLink>
        <RouterLink :class="navClass(isFavorites)" to="/favorites">收藏</RouterLink>
      </nav>

      <div class="app-topbar__actions">
        <RouterLink
          v-if="auth.isAuthenticated && !isHome && !isMap"
          class="app-topbar__cta"
          to="/"
        >
          开始规划
        </RouterLink>
        <RouterLink
          v-if="!auth.isAuthenticated"
          class="app-login-glow"
          :to="{ name: 'login', query: { redirect: route.fullPath } }"
          aria-label="登录 TripMate"
        >
          <span class="app-login-glow__inner">
            <UserRound :size="22" :stroke-width="1.8" />
            <span>登录</span>
          </span>
        </RouterLink>
        <RouterLink
          v-else
          class="app-profile-link"
          :class="{ 'is-active': isProfile }"
          to="/profile"
          :aria-label="`${auth.user?.display_name || '我的'}，个人资料`"
        >
          <span>{{ auth.initials.slice(0, 1) }}</span>
        </RouterLink>
        <button
          class="app-menu-toggle"
          type="button"
          :aria-expanded="mobileMenuOpen"
          aria-label="打开导航"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <X v-if="mobileMenuOpen" :size="20" :stroke-width="1.8" />
          <Menu v-else :size="20" :stroke-width="1.8" />
        </button>
      </div>
    </header>

    <Transition name="mobile-nav">
      <nav v-if="mobileMenuOpen" class="mobile-nav" aria-label="移动端导航">
        <RouterLink :class="navClass(isHome)" to="/">对话</RouterLink>
        <RouterLink :class="navClass(isTrips)" to="/trips">行程</RouterLink>
        <RouterLink :class="navClass(isPlaces)" to="/places">探索</RouterLink>
        <RouterLink :class="navClass(isFavorites)" to="/favorites">
          <Heart :size="15" />
          收藏
        </RouterLink>
        <RouterLink
          v-if="auth.isAuthenticated"
          :class="navClass(isProfile)"
          to="/profile"
        >
          我的
        </RouterLink>
        <RouterLink
          v-else
          :to="{ name: 'login', query: { redirect: isPublicHome ? '/' : route.fullPath } }"
        >
          登录
        </RouterLink>
      </nav>
    </Transition>

    <main class="app-main">
      <RouterView v-slot="{ Component }">
        <component :is="Component" />
      </RouterView>
    </main>
  </div>
</template>
