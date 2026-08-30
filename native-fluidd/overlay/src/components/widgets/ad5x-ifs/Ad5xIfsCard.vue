<template>
  <collapsable-card
    :title="$t('app.ad5x_ifs.title').toString()"
    icon="$filament"
    draggable
    layout-path="dashboard.ad5x-ifs-card"
    card-classes="ad5x-ifs-card"
  >
    <template #title>
      <div class="ifs-card-title">
        <div class="ifs-card-title__main">
          <v-icon left>
            $filament
          </v-icon>
          <span class="font-weight-light ifs-card-title__text">
            {{ $t('app.ad5x_ifs.title') }}
          </span>
        </div>

        <div class="ifs-header-actions ifs-header-actions--mobile">
          <v-chip
            x-small
            label
            outlined
            :color="connected ? 'success' : 'warning'"
          >
            {{ connected ? $t('app.ad5x_ifs.connected') : $t('app.ad5x_ifs.disconnected') }}
          </v-chip>

          <app-btn
            x-small
            outlined
            color="primary"
            @click.stop="openManager"
          >
            {{ $t('app.ad5x_ifs.manage') }}
          </app-btn>
        </div>
      </div>
    </template>

    <template #menu>
      <div class="ifs-header-actions ifs-header-actions--desktop">
        <v-chip
          small
          label
          outlined
          :color="connected ? 'success' : 'warning'"
        >
          {{ connected ? $t('app.ad5x_ifs.connected') : $t('app.ad5x_ifs.disconnected') }}
        </v-chip>

        <app-btn
          small
          outlined
          color="primary"
          @click.stop="openManager"
        >
          {{ $t('app.ad5x_ifs.manage') }}
        </app-btn>
      </div>
    </template>

    <v-card-text class="ifs-card-content pt-3 pb-3">
      <v-alert
        v-if="lastError"
        type="warning"
        dense
        text
        class="mb-3"
      >
        {{ $t('app.ad5x_ifs.api_unavailable') }}: {{ lastError }}
      </v-alert>

      <div class="ifs-slots">
        <button
          v-for="slot in 4"
          :key="`ifs-slot-${slot}`"
          type="button"
          class="ifs-slot"
          :class="{
            'ifs-slot--selected': selectedSlot === slot,
            'ifs-slot--active': activeSlot === slot,
            'ifs-slot--assigned': Boolean(spoolForSlot(slot)),
            'ifs-slot--empty': !spoolForSlot(slot)
          }"
          @click="selectedSlot = slot"
        >
          <div class="ifs-slot__top">
            <span class="ifs-slot__number">{{ slot }}</span>
            <span
              class="ifs-slot__name"
              :title="spoolForSlot(slot) ? nameOf(spoolForSlot(slot)) : ''"
            >
              {{ spoolForSlot(slot) ? nameOf(spoolForSlot(slot)) : '—' }}
            </span>
            <v-icon
              v-if="activeSlot === slot"
              x-small
              color="success"
            >
              $check
            </v-icon>
            <span v-else class="ifs-slot__check-spacer" />
          </div>

          <div class="ifs-slot__body">
            <div
              class="ifs-spool ifs-spool--small"
              :class="{ 'ifs-spool--empty': !spoolForSlot(slot) }"
            >
              <div
                class="ifs-spool__winding"
                :style="{ background: spoolGradient(spoolForSlot(slot)) }"
              />
              <div class="ifs-spool__hub" />
              <div class="ifs-spool__hole" />
            </div>

            <div
              class="ifs-slot__vendor"
              :title="spoolForSlot(slot) ? vendorOf(spoolForSlot(slot)) : ''"
            >
              {{ spoolForSlot(slot) ? vendorOf(spoolForSlot(slot)) : $t('app.ad5x_ifs.unassigned') }}
            </div>
          </div>

          <div v-if="spoolForSlot(slot)" class="ifs-slot__meta">
            <span class="ifs-slot__pill">ID {{ spoolIdForSlot(slot) }}</span>
            <span class="ifs-slot__pill">{{ materialOf(spoolForSlot(slot)) }}</span>
            <span class="ifs-slot__stock">{{ compactStock(spoolForSlot(slot)) }}</span>
          </div>
          <div v-else class="ifs-slot__empty-label">—</div>

          <div v-if="spoolForSlot(slot)" class="ifs-slot__progress">
            <div
              class="ifs-slot__progress-value"
              :style="{
                width: `${percentage(spoolForSlot(slot))}%`,
                background: spoolGradient(spoolForSlot(slot))
              }"
            />
          </div>
        </button>
      </div>

      <div v-if="focusedSpool" class="ifs-summary mt-3">
        <div class="ifs-summary__label">
          <span>IFS {{ focusedSlot }} · {{ nameOf(focusedSpool) }}</span>
          <strong>{{ weightLabel(focusedSpool) }} · {{ percentage(focusedSpool) }}%</strong>
        </div>
        <div class="ifs-summary__progress">
          <div
            class="ifs-summary__progress-value"
            :style="{
              width: `${percentage(focusedSpool)}%`,
              background: spoolGradient(focusedSpool)
            }"
          />
        </div>
      </div>

      <div class="ifs-footer mt-4">
        <span class="ifs-meta-pill ifs-meta-pill--primary">
          {{ $t('app.ad5x_ifs.active_slot') }}: IFS {{ activeSlot }}
        </span>
        <span class="ifs-meta-pill">
          {{ $t('app.ad5x_ifs.assigned') }}: {{ assignedCount }}/4
        </span>
        <span
          v-if="currentSpoolLabel !== '—'"
          class="ifs-meta-pill ifs-meta-pill--wide"
        >
          {{ $t('app.ad5x_ifs.moonraker_spool') }}: {{ currentSpoolLabel }}
        </span>
      </div>
    </v-card-text>

    <template #collapsed-content>
      <v-progress-linear
        :value="connected ? 100 : 0"
        :color="connected ? 'success' : 'warning'"
        :height="4"
      />
    </template>
  </collapsable-card>
</template>

<script lang="ts">
import Vue from 'vue'

type IfsStatus = {
  active_slot?: number
  moonraker_spool_id?: number | null
  spoolman_connected?: boolean
  assignments?: Record<string, number | null>
}

type IfsSpool = {
  id: number
  remaining_weight?: number | null
  initial_weight?: number | null
  filament?: {
    name?: string | null
    material?: string | null
    color_hex?: string | null
    multi_color_hexes?: string | null
    multi_color_direction?: string | null
    vendor?: {
      name?: string | null
    } | null
  } | null
}

const API_REFRESH_MS = 15000

export default Vue.extend({
  name: 'Ad5xIfsCard',

  data () {
    return {
      status: null as IfsStatus | null,
      spools: [] as IfsSpool[],
      selectedSlot: null as number | null,
      lastError: null as string | null,
      refreshTimer: null as number | null
    }
  },

  computed: {
    apiBase (): string {
      return `${window.location.protocol}//${window.location.hostname}:7913`
    },

    connected (): boolean {
      return Boolean(this.status?.spoolman_connected) && this.lastError == null
    },

    activeSlot (): number {
      const value = Number(this.status?.active_slot || 1)
      return value >= 1 && value <= 4 ? value : 1
    },

    assignments (): Record<string, number | null> {
      return this.status?.assignments || {}
    },

    focusedSlot (): number {
      return this.selectedSlot != null ? this.selectedSlot : this.activeSlot
    },

    focusedSpool (): IfsSpool | null {
      return this.spoolForSlot(this.focusedSlot)
    },

    assignedCount (): number {
      let count = 0
      for (let slot = 1; slot <= 4; slot++) {
        if (this.assignments[String(slot)] != null) count++
      }
      return count
    },

    currentSpoolLabel (): string {
      const spoolId = this.status?.moonraker_spool_id
      if (spoolId == null) return '—'

      const spool = this.spools.find(item => Number(item.id) === Number(spoolId))
      if (!spool) return `ID ${spoolId}`

      return `${this.vendorOf(spool)} · ${this.nameOf(spool)}`
    }
  },

  mounted () {
    void this.refreshData()
    this.refreshTimer = window.setInterval(() => {
      void this.refreshData()
    }, API_REFRESH_MS)
  },

  beforeDestroy () {
    if (this.refreshTimer != null) {
      window.clearInterval(this.refreshTimer)
      this.refreshTimer = null
    }
  },

  methods: {
    async fetchJson<T> (url: string): Promise<T> {
      const response = await window.fetch(url, { cache: 'no-store' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return await response.json() as T
    },

    async refreshData () {
      try {
        const [status, spools] = await Promise.all([
          this.fetchJson<IfsStatus>(`${this.apiBase}/api/status`),
          this.fetchJson<IfsSpool[]>(`${this.apiBase}/api/spools`)
        ])

        this.status = status || null
        this.spools = Array.isArray(spools) ? spools : []
        this.lastError = null

      } catch (error) {
        this.lastError = error instanceof Error ? error.message : String(error)
      }
    },

    openManager () {
      window.open(`${this.apiBase}/`, '_blank', 'noopener,noreferrer')
    },

    spoolForSlot (slot: number): IfsSpool | null {
      const spoolId = this.assignments[String(slot)]
      if (spoolId == null) return null
      return this.spools.find(item => Number(item.id) === Number(spoolId)) || null
    },

    spoolIdForSlot (slot: number): string {
      const spool = this.spoolForSlot(slot)
      return spool ? String(spool.id) : '—'
    },

    normalizeHex (value: unknown): string | null {
      if (value == null) return null
      const normalized = String(value).trim().replace(/^#/, '')
      return /^[0-9a-fA-F]{6}$/.test(normalized)
        ? `#${normalized.toUpperCase()}`
        : null
    },

    spoolColors (spool: IfsSpool | null): string[] {
      if (!spool?.filament) return ['#8E939B']

      const multi = String(spool.filament.multi_color_hexes || '')
        .split(',')
        .map(value => this.normalizeHex(value))
        .filter((value): value is string => value != null)

      if (multi.length > 0) return multi

      const single = this.normalizeHex(spool.filament.color_hex)
      return single ? [single] : ['#8E939B']
    },

    spoolGradient (spool: IfsSpool | null): string {
      const colors = this.spoolColors(spool)
      if (colors.length === 1) return colors[0]

      const width = 100 / colors.length
      const stops: string[] = []
      colors.forEach((color, index) => {
        const start = (index * width).toFixed(3)
        const end = ((index + 1) * width).toFixed(3)
        stops.push(`${color} ${start}%`, `${color} ${end}%`)
      })

      const direction = String(spool?.filament?.multi_color_direction || '').toLowerCase()
      const angle = direction === 'longitudinal' ? '135deg' : '90deg'
      return `linear-gradient(${angle}, ${stops.join(', ')})`
    },

    materialOf (spool: IfsSpool | null): string {
      return spool?.filament?.material || '—'
    },

    vendorOf (spool: IfsSpool | null): string {
      return spool?.filament?.vendor?.name || '—'
    },

    nameOf (spool: IfsSpool | null): string {
      return spool?.filament?.name || this.$t('app.ad5x_ifs.unnamed').toString()
    },

    remainingWeight (spool: IfsSpool | null): number {
      return Number(spool?.remaining_weight || 0)
    },

    initialWeight (spool: IfsSpool | null): number {
      return Number(spool?.initial_weight || 0)
    },

    percentage (spool: IfsSpool | null): number {
      const total = this.initialWeight(spool)
      if (total <= 0) return 0
      const value = Math.round(this.remainingWeight(spool) * 100 / total)
      return Math.max(0, Math.min(100, value))
    },

    weightLabel (spool: IfsSpool | null): string {
      return `${Math.round(this.remainingWeight(spool))} g / ${Math.round(this.initialWeight(spool))} g`
    },

    compactStock (spool: IfsSpool | null): string {
      const remaining = Math.round(this.remainingWeight(spool))
      const total = this.initialWeight(spool)
      return total > 0
        ? `${remaining} g · ${this.percentage(spool)}%`
        : `${remaining} g`
    }
  }
})
</script>

<style lang="scss" scoped>
.ad5x-ifs-card {
  overflow: hidden;
  border: 1px solid rgba(127, 127, 127, .24);
  box-shadow: 0 2px 12px rgba(0, 0, 0, .14) !important;
}

.ifs-card-content {
  background: rgba(0, 0, 0, .045);
}

.ifs-card-title {
  min-width: 0;
}

.ifs-card-title__main {
  display: flex;
  min-width: 0;
  align-items: center;
}

.ifs-card-title__text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ifs-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ifs-header-actions--mobile {
  display: none;
}

.ifs-slots {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
}

.ifs-slot {
  position: relative;
  min-width: 0;
  padding: 8px 9px 9px;
  border: 1px solid rgba(127, 127, 127, .25);
  border-radius: 10px;
  background: rgba(127, 127, 127, .055);
  width: 100%;
  appearance: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  opacity: .82;
  transition: background-color .15s ease, border-color .15s ease, box-shadow .15s ease, opacity .15s ease;
}

.ifs-slot:hover {
  background: rgba(127, 127, 127, .09);
  opacity: 1;
}

.ifs-slot--assigned {
  opacity: 1;
}

.ifs-slot--empty {
  opacity: .58;
}

.ifs-slot--selected {
  border: 2px solid var(--v-primary-base, #2196f3);
  background: rgba(127, 127, 127, .12);
  box-shadow: inset 4px 0 0 var(--v-primary-base, #2196f3);
  opacity: 1;
}

.ifs-slot--active:not(.ifs-slot--selected) {
  border: 2px solid var(--v-success-base, #4caf50);
  background: rgba(127, 127, 127, .085);
}

.ifs-slot--active .ifs-slot__number {
  color: var(--v-success-base, #4caf50);
  font-weight: 800;
}

.ifs-slot__top {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) 18px;
  gap: 4px;
  min-height: 18px;
  align-items: center;
}

.ifs-slot__number {
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
}

.ifs-slot__name {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.15;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ifs-slot__check-spacer {
  width: 18px;
  height: 1px;
}

.ifs-slot__body {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 7px;
  align-items: center;
  margin: 5px 0 7px;
}

.ifs-slot__vendor {
  min-width: 0;
  overflow: hidden;
  font-size: 10px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: .82;
}

.ifs-slot__meta {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.ifs-slot__pill {
  flex: 0 0 auto;
  max-width: 100%;
  overflow: hidden;
  padding: 2px 5px;
  border: 1px solid rgba(127, 127, 127, .22);
  border-radius: 5px;
  background: rgba(127, 127, 127, .06);
  font-size: 9px;
  font-weight: 700;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ifs-slot__stock {
  min-width: 0;
  margin-left: auto;
  overflow: hidden;
  font-size: 9px;
  font-weight: 700;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: .88;
}

.ifs-slot__empty-label {
  min-height: 16px;
  font-size: 10px;
  line-height: 1.3;
  opacity: .58;
}

.ifs-slot__progress {
  height: 5px;
  margin-top: 7px;
  overflow: hidden;
  border: 1px solid rgba(127, 127, 127, .18);
  border-radius: 999px;
  background: rgba(127, 127, 127, .20);
}

.ifs-slot__progress-value {
  height: 100%;
  border-radius: inherit;
  box-shadow: inset 0 0 0 1px rgba(127, 127, 127, .18);
  transition: width .2s ease;
}

.ifs-summary {
  min-width: 0;
}

.ifs-summary__label {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 11px;
  line-height: 1.35;
}

.ifs-summary__label > span {
  min-width: 0;
  overflow: hidden;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ifs-summary__label > strong {
  flex: 0 0 auto;
  font-weight: 800;
}

.ifs-summary__progress {
  height: 8px;
  margin-top: 5px;
  overflow: hidden;
  border: 1px solid rgba(127, 127, 127, .18);
  border-radius: 999px;
  background: rgba(127, 127, 127, .20);
}

.ifs-summary__progress-value {
  height: 100%;
  border-radius: inherit;
  box-shadow: inset 0 0 0 1px rgba(127, 127, 127, .18);
  transition: width .2s ease;
}

.ifs-spool {
  position: relative;
  flex: 0 0 auto;
  border-radius: 50%;
  background: rgba(127, 127, 127, .13);
  box-shadow: 0 2px 7px rgba(0, 0, 0, .18), inset 0 0 0 1px rgba(127, 127, 127, .28);
}

.ifs-spool--small {
  width: 36px;
  height: 36px;
  margin: 0 auto;
}

.ifs-spool__winding {
  position: absolute;
  inset: 4px;
  overflow: hidden;
  border-radius: 50%;
  background: #8e939b;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .14);
}

.ifs-spool__hub {
  position: absolute;
  inset: 31%;
  border-radius: 50%;
  background: rgba(45, 52, 64, .92);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .12);
}

.ifs-spool__hole {
  position: absolute;
  inset: 43%;
  border-radius: 50%;
  background: rgba(10, 14, 20, .92);
}

.ifs-spool--empty {
  opacity: .42;
}

.ifs-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.ifs-meta-pill {
  max-width: 100%;
  overflow: hidden;
  padding: 3px 7px;
  border: 1px solid rgba(127, 127, 127, .22);
  border-radius: 6px;
  background: rgba(127, 127, 127, .06);
  font-size: 10px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: .84;
}

.ifs-meta-pill--primary {
  border-color: var(--v-primary-base, #2196f3);
  color: var(--v-primary-base, #2196f3);
  opacity: 1;
}

.ifs-meta-pill--wide {
  flex: 0 1 auto;
}

@media (max-width: 600px) {
  .ifs-card-title {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    white-space: normal;
  }

  .ifs-card-title__main {
    width: 100%;
  }

  .ifs-header-actions--desktop {
    display: none;
  }

  .ifs-header-actions--mobile {
    display: flex;
    width: 100%;
    flex-wrap: wrap;
    gap: 4px;
    padding-top: 2px;
  }

  .ifs-slots {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ifs-meta-pill--wide {
    flex-basis: 100%;
  }
}
</style>