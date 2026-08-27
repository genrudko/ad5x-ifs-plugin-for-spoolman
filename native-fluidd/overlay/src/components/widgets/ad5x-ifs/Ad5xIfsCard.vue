<template>
  <collapsable-card
    :title="$t('app.ad5x_ifs.title').toString()"
    icon="$filament"
    draggable
    layout-path="dashboard.ad5x-ifs-card"
    card-classes="ad5x-ifs-card"
  >
    <template #menu>
      <v-chip
        small
        label
        outlined
        class="me-2 my-1"
        :color="connected ? 'success' : 'warning'"
      >
        {{ connected ? $t('app.ad5x_ifs.connected') : $t('app.ad5x_ifs.disconnected') }}
      </v-chip>

      <app-btn
        small
        text
        class="me-1 my-1"
        @click="openManager"
      >
        {{ $t('app.ad5x_ifs.manage') }}
      </app-btn>
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
            <v-icon
              v-if="activeSlot === slot"
              x-small
              color="success"
            >
              $check
            </v-icon>
          </div>

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

          <div class="ifs-slot__material">
            {{ spoolForSlot(slot) ? materialOf(spoolForSlot(slot)) : '—' }}
          </div>
        </button>
      </div>

      <v-divider class="ifs-divider my-3" />

      <div v-if="selectedSpool" class="ifs-detail">
        <div class="ifs-spool ifs-spool--large">
          <div
            class="ifs-spool__winding"
            :style="{ background: spoolGradient(selectedSpool) }"
          />
          <div class="ifs-spool__hub" />
          <div class="ifs-spool__hole" />
        </div>

        <div class="ifs-detail__body">
          <div class="d-flex align-start justify-space-between flex-wrap gap-2">
            <div class="min-width-0">
              <div class="text-subtitle-1 font-weight-bold text-truncate">
                {{ nameOf(selectedSpool) }}
              </div>
              <div class="text-caption text--secondary">
                IFS {{ selectedSlot }} · {{ vendorOf(selectedSpool) }}
              </div>
            </div>

            <div class="d-flex flex-wrap justify-end">
              <v-chip
                x-small
                label
                outlined
                class="ms-1 mb-1"
              >
                {{ materialOf(selectedSpool) }}
              </v-chip>
              <v-chip
                x-small
                label
                outlined
                class="ms-1 mb-1"
              >
                ID {{ selectedSpool.id }}
              </v-chip>
              <v-chip
                v-if="activeSlot === selectedSlot"
                x-small
                label
                outlined
                color="success"
                class="ms-1 mb-1"
              >
                {{ $t('app.ad5x_ifs.active') }}
              </v-chip>
            </div>
          </div>

          <div class="ifs-progress-label mt-3">
            <span>{{ $t('app.ad5x_ifs.remaining') }}</span>
            <strong>{{ weightLabel(selectedSpool) }} · {{ percentage(selectedSpool) }}%</strong>
          </div>

          <div class="ifs-progress mt-1">
            <div
              class="ifs-progress__value"
              :style="{ width: `${percentage(selectedSpool)}%` }"
            />
          </div>
        </div>
      </div>

      <div v-else class="ifs-detail">
        <div class="ifs-spool ifs-spool--large ifs-spool--empty">
          <div class="ifs-spool__winding" />
          <div class="ifs-spool__hub" />
          <div class="ifs-spool__hole" />
        </div>

        <div class="ifs-detail__body">
          <div class="text-subtitle-2 font-weight-bold">
            IFS {{ selectedSlot }}
          </div>
          <div class="text-caption text--secondary mt-1">
            {{ $t('app.ad5x_ifs.unassigned') }}
          </div>
          <div class="text-caption text--secondary mt-1">
            {{ $t('app.ad5x_ifs.unassigned_hint') }}
          </div>
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
      selectedSlot: 1,
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

    selectedSpool (): IfsSpool | null {
      return this.spoolForSlot(this.selectedSlot)
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

        if (this.selectedSlot < 1 || this.selectedSlot > 4) {
          this.selectedSlot = this.activeSlot
        }
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

.ifs-slots {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
}

.ifs-slot {
  position: relative;
  min-width: 0;
  padding: 9px 7px 8px;
  border: 1px solid rgba(127, 127, 127, .25);
  border-radius: 10px;
  background: rgba(127, 127, 127, .055);
  color: inherit;
  cursor: pointer;
  opacity: .82;
  transition: background-color .15s ease, border-color .15s ease, box-shadow .15s ease, opacity .15s ease;
}

.ifs-slot:hover {
  background: rgba(127, 127, 127, .11);
  opacity: 1;
}

.ifs-slot--assigned {
  opacity: 1;
}

.ifs-slot--empty {
  opacity: .58;
}

.ifs-slot--selected {
  border-color: var(--v-primary-base, #2196f3);
  background: rgba(127, 127, 127, .10);
  box-shadow: inset 3px 0 0 var(--v-primary-base, #2196f3), inset 0 0 0 1px rgba(127, 127, 127, .10);
  opacity: 1;
}

.ifs-slot--active:not(.ifs-slot--selected) {
  border-color: var(--v-success-base, #4caf50);
}

.ifs-slot--active .ifs-slot__number {
  color: var(--v-success-base, #4caf50);
  font-weight: 800;
}

.ifs-slot__top {
  display: flex;
  min-height: 18px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
}

.ifs-slot__number {
  font-size: 11px;
  font-weight: 700;
}

.ifs-slot__material {
  margin-top: 6px;
  overflow: hidden;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ifs-divider {
  opacity: .72;
}

.ifs-detail {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  min-width: 0;
  padding: 1px 2px;
}

.ifs-detail__body,
.min-width-0 {
  min-width: 0;
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

.ifs-spool--large {
  width: 58px;
  height: 58px;
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

.ifs-progress-label {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 11px;
}

.ifs-progress-label > span {
  opacity: .76;
}

.ifs-progress-label > strong {
  font-weight: 700;
}

.ifs-progress {
  height: 7px;
  overflow: hidden;
  border: 1px solid rgba(127, 127, 127, .16);
  border-radius: 999px;
  background: rgba(127, 127, 127, .20);
}

.ifs-progress__value {
  height: 100%;
  border-radius: inherit;
  background: var(--v-primary-base, #2196f3);
  transition: width .2s ease;
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
  .ifs-slots {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ifs-detail {
    gap: 10px;
  }

  .ifs-meta-pill--wide {
    flex-basis: 100%;
  }
}
</style>