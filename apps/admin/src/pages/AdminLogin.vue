<!-- 文件说明：管理后台页面：AdminLogin。 -->
<script setup lang="ts">
import { ArrowRight, LockKeyhole, Mail, ShieldCheck } from "lucide-vue-next";
import { reactive } from "vue";

defineProps<{
  loading: boolean;
  error: string;
}>();

const emit = defineEmits<{
  login: [email: string, password: string];
}>();

const form = reactive({
  email: "",
  password: "",
});

function submit(): void {
  emit("login", form.email.trim(), form.password);
}
</script>

<template>
  <main class="admin-login">
    <section class="admin-login__intro">
      <span class="admin-login__mark"><ShieldCheck :size="23" /></span>
      <p>TripMate Operations</p>
      <h1>管理后台</h1>
      <span>只允许管理员账号登录。</span>
    </section>

    <form class="admin-login__form" @submit.prevent="submit">
      <header>
        <strong>管理员登录</strong>
        <small>使用 TripMate 账号</small>
      </header>

      <label>
        <span>邮箱</span>
        <span class="admin-input">
          <Mail :size="16" />
          <input
            v-model.trim="form.email"
            type="email"
            autocomplete="email"
            required
            placeholder="admin@example.com"
          />
        </span>
      </label>

      <label>
        <span>密码</span>
        <span class="admin-input">
          <LockKeyhole :size="16" />
          <input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            required
            placeholder="输入密码"
          />
        </span>
      </label>

      <p v-if="error" class="admin-error" role="alert">{{ error }}</p>

      <button class="admin-button admin-button--primary" type="submit" :disabled="loading">
        <span>{{ loading ? "验证中" : "进入后台" }}</span>
        <ArrowRight :size="16" />
      </button>
    </form>
  </main>
</template>
