<script setup lang="ts">
import { computed, type Component } from 'vue'
import {
  AirVent,
  Blinds,
  BookOpen,
  Bot,
  Briefcase,
  Building2,
  Clapperboard,
  CloudSun,
  Coffee,
  Cpu,
  DoorOpen,
  Droplets,
  Film,
  Gauge,
  Home,
  Lamp,
  LampCeiling,
  LampDesk,
  Leaf,
  Lightbulb,
  Moon,
  Plug,
  Shield,
  Sparkles,
  Speaker,
  Sun,
  Sunrise,
  Thermometer,
  Users,
  Wind,
  Zap,
} from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    icon?: string
    size?: number
    strokeWidth?: number
  }>(),
  { icon: 'cpu', size: 18, strokeWidth: 1.8 },
)

const iconMap: Record<string, Component> = {
  'ceiling-light': LampCeiling,
  'lamp-ceiling': LampCeiling,
  lightbulb: Lightbulb,
  lamp: Lamp,
  'lamp-desk': LampDesk,
  'air-vent': AirVent,
  blinds: Blinds,
  wind: Wind,
  droplets: Droplets,
  plug: Plug,
  speaker: Speaker,
  bot: Bot,
  thermometer: Thermometer,
  home: Home,
  'door-open': DoorOpen,
  clapperboard: Clapperboard,
  moon: Moon,
  sunrise: Sunrise,
  sun: Sun,
  leaf: Leaf,
  sparkles: Sparkles,
  'book-open': BookOpen,
  users: Users,
  shield: Shield,
  zap: Zap,
  film: Film,
  coffee: Coffee,
  briefcase: Briefcase,
  building: Building2,
  gauge: Gauge,
  'cloud-sun': CloudSun,
  cpu: Cpu,
}

const iconComponent = computed<Component>(() => iconMap[props.icon] || Cpu)
</script>

<template>
  <component :is="iconComponent" :size="size" :stroke-width="strokeWidth" aria-hidden="true" />
</template>
