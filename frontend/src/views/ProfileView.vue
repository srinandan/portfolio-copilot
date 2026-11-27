<template>
  <div class="flex flex-col gap-lg w-full" data-testid="profile-view">
    <!-- Header -->
    <header class="flex flex-col md:flex-row md:items-end justify-between gap-md pb-md border-b border-outline-variant">
      <div class="flex flex-col gap-1">
        <h1 class="font-display text-page-title font-medium text-on-background">User Profile &amp; Policy Settings</h1>
        <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
          Manage personal context, financial goals, risk calibration, liabilities, and autonomous governance guardrails.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-3 shrink-0">
        <span
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md font-sans text-meta font-semibold border tabular-nums"
          :class="[
            hasActiveIPS
              ? 'bg-tertiary-fixed text-on-tertiary-fixed border-tertiary-fixed-dim'
              : 'bg-secondary-fixed text-on-secondary-fixed border-secondary-fixed-dim'
          ]"
          data-testid="badge-ips-status"
        >
          <span class="material-symbols-outlined text-[16px]" aria-hidden="true">
            {{ hasActiveIPS ? 'check_circle' : 'schedule' }}
          </span>
          <span>{{ hasActiveIPS ? `Active IPS (v${ipsVersion})` : 'Draft Policy' }}</span>
        </span>

        <button
          type="button"
          class="px-4 py-2 bg-surface-container-lowest hover:bg-surface-container-low text-on-surface font-sans text-meta font-medium rounded-md border border-outline-variant transition-colors duration-150 ease-desk inline-flex items-center gap-1.5"
          data-testid="btn-launch-wizard"
          @click="router.push('/onboarding')"
        >
          <span class="material-symbols-outlined text-primary text-[16px]" aria-hidden="true">tune</span>
          Run Guided Setup
        </button>
      </div>
    </header>

    <!-- Status Banners -->
    <div
      v-if="saveSuccess"
      class="px-md py-3 rounded-lg bg-tertiary-fixed/50 border border-tertiary-fixed-dim text-on-tertiary-fixed flex items-center justify-between gap-md"
      data-testid="profile-save-success"
    >
      <div class="flex items-center gap-2.5">
        <span class="material-symbols-outlined text-on-tertiary-container text-[20px]" aria-hidden="true">check_circle</span>
        <span class="font-sans text-body font-medium">Profile and Investment Policy Statement saved and synchronized.</span>
      </div>
      <button type="button" class="font-sans text-meta font-medium hover:underline shrink-0" @click="saveSuccess = false">
        Dismiss
      </button>
    </div>

    <div
      v-if="saveError"
      class="px-md py-3 rounded-lg bg-error-container border border-error/30 text-on-error-container flex items-center justify-between gap-md"
      data-testid="profile-save-error"
    >
      <div class="flex items-center gap-2.5">
        <span class="material-symbols-outlined text-error text-[20px]" aria-hidden="true">error</span>
        <span class="font-sans text-body font-medium">{{ saveError }}</span>
      </div>
      <button type="button" class="font-sans text-meta font-medium hover:underline shrink-0" @click="saveError = null">
        Dismiss
      </button>
    </div>

    <!-- Unified Summary Strip -->
    <section class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet grid grid-cols-2 lg:grid-cols-4 divide-y lg:divide-y-0 lg:divide-x divide-outline-variant overflow-hidden">
      <div class="p-md flex flex-col gap-0.5">
        <span class="font-sans text-meta text-on-surface-variant">Risk tolerance</span>
        <span class="font-sans text-body font-semibold capitalize text-on-surface" data-testid="metric-risk-tolerance">
          {{ riskTolerance }}
        </span>
      </div>
      <div class="p-md flex flex-col gap-0.5 border-l border-outline-variant lg:border-l-0">
        <span class="font-sans text-meta text-on-surface-variant">Planning horizon</span>
        <span class="font-sans text-body font-semibold text-on-surface tabular-nums" data-testid="metric-time-horizon">
          {{ timeHorizonYears }} Years
        </span>
      </div>
      <div class="p-md flex flex-col gap-0.5">
        <span class="font-sans text-meta text-on-surface-variant">Reported liabilities</span>
        <span class="font-sans text-body font-semibold text-on-surface tabular-nums" data-testid="metric-total-liabilities">
          ${{ totalLiabilities.toLocaleString() }}
        </span>
      </div>
      <div class="p-md flex flex-col gap-0.5 border-l border-outline-variant lg:border-l-0">
        <span class="font-sans text-meta text-on-surface-variant">Concentration limit</span>
        <span class="font-sans text-body font-semibold text-on-surface tabular-nums" data-testid="metric-concentration-limit">
          {{ concentrationLimit }}% max / ticker
        </span>
      </div>
    </section>

    <!-- Underline Section Tabs -->
    <div
      role="tablist"
      aria-label="Profile sections"
      class="flex items-center gap-1 border-b border-outline-variant overflow-x-auto"
      data-testid="profile-tabs"
    >
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.id"
        class="relative px-3.5 py-3 font-sans text-meta transition-colors duration-150 ease-desk inline-flex items-center gap-1.5 whitespace-nowrap shrink-0"
        :class="[
          activeTab === tab.id
            ? 'text-primary font-semibold'
            : 'text-on-surface-variant hover:text-on-surface font-medium'
        ]"
        :data-testid="`tab-${tab.id}`"
        @click="activeTab = tab.id"
      >
        <span class="material-symbols-outlined text-[17px]" aria-hidden="true">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
        <span
          v-if="activeTab === tab.id"
          class="absolute bottom-0 inset-x-2 h-[2px] bg-primary rounded-t-full"
          aria-hidden="true"
        ></span>
      </button>
    </div>

    <!-- Main Settings Form -->
    <form class="flex flex-col gap-lg" @submit.prevent="handleSave">
      <!-- TAB 1: Personal & Family -->
      <div v-show="activeTab === 'personal'" class="flex flex-col gap-lg" data-testid="section-personal">
        <!-- Personal Demographics -->
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <h2 class="font-sans text-heading font-semibold text-on-surface border-b border-outline-variant pb-3">
            Personal Demographics
          </h2>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Full name</label>
              <input
                v-model="userProfile.full_name"
                type="text"
                placeholder="e.g. Alex Mercer"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
                data-testid="input-full-name"
              />
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Email address</label>
              <input
                v-model="userProfile.email"
                type="email"
                placeholder="e.g. alex.mercer@example.com"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
                data-testid="input-email"
              />
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Date of birth</label>
              <input
                v-model="userProfile.date_of_birth"
                type="date"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
                data-testid="input-dob"
                @change="calculateAgeFromDOB"
              />
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Age</label>
              <input
                v-model.number="userProfile.age"
                type="number"
                min="0"
                max="150"
                placeholder="e.g. 46"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
                data-testid="input-age"
              />
            </div>

            <div class="flex flex-col gap-1.5 md:col-span-2">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Marital status</label>
              <select
                v-model="userProfile.marital_status"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
                data-testid="select-marital-status"
              >
                <option value="single">Single</option>
                <option value="married">Married</option>
                <option value="partnered">Partnered</option>
                <option value="divorced">Divorced</option>
                <option value="widowed">Widowed</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>
        </section>

        <!-- Family & Dependents -->
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant pb-3 gap-md">
            <h2 class="font-sans text-heading font-semibold text-on-surface">Family &amp; Dependents</h2>
            <button
              type="button"
              class="px-3 py-1.5 font-sans text-meta font-medium text-primary hover:bg-surface-container-low rounded-md border border-outline-variant inline-flex items-center gap-1 transition-colors duration-150 ease-desk"
              data-testid="btn-add-family-member"
              @click="addFamilyMember"
            >
              <span class="material-symbols-outlined text-[16px]" aria-hidden="true">add</span>
              Add member
            </button>
          </div>

          <div class="flex flex-col gap-md">
            <div class="flex items-center gap-md flex-wrap">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Number of financial dependents</label>
              <input
                v-model.number="userProfile.dependents_count"
                type="number"
                min="0"
                class="w-24 px-3 py-1.5 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-dependents-count"
              />
            </div>

            <div
              v-if="userProfile.family_members && userProfile.family_members.length > 0"
              class="divide-y divide-outline-variant/70 border-t border-outline-variant/70"
            >
              <div
                v-for="(member, idx) in userProfile.family_members"
                :key="idx"
                class="grid grid-cols-12 gap-3 items-end py-3"
                data-testid="family-member-row"
              >
                <div class="col-span-12 sm:col-span-5 flex flex-col gap-1">
                  <span class="font-sans text-meta text-on-surface-variant">Name</span>
                  <input
                    v-model="member.name"
                    type="text"
                    placeholder="Name"
                    class="px-3 py-1.5 font-sans text-body bg-surface border border-outline-variant rounded-md text-on-surface focus:bg-surface-container-lowest"
                  />
                </div>
                <div class="col-span-7 sm:col-span-4 flex flex-col gap-1">
                  <span class="font-sans text-meta text-on-surface-variant">Relationship</span>
                  <select
                    v-model="member.relationship"
                    class="px-3 py-1.5 font-sans text-body bg-surface border border-outline-variant rounded-md text-on-surface focus:bg-surface-container-lowest"
                  >
                    <option value="spouse">Spouse</option>
                    <option value="child">Child</option>
                    <option value="parent">Parent</option>
                    <option value="sibling">Sibling</option>
                    <option value="dependent">Dependent</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div class="col-span-3 sm:col-span-2 flex flex-col gap-1">
                  <span class="font-sans text-meta text-on-surface-variant">Age</span>
                  <input
                    v-model.number="member.age"
                    type="number"
                    min="0"
                    max="150"
                    class="px-3 py-1.5 font-sans text-body tabular-nums bg-surface border border-outline-variant rounded-md text-on-surface focus:bg-surface-container-lowest"
                  />
                </div>
                <div class="col-span-2 sm:col-span-1 flex justify-end pb-1">
                  <button
                    type="button"
                    class="text-on-surface-variant hover:text-error p-1.5 rounded-md hover:bg-error-container/40 transition-colors duration-150 ease-desk"
                    title="Remove family member"
                    data-testid="btn-remove-family-member"
                    @click="removeFamilyMember(idx)"
                  >
                    <span class="material-symbols-outlined text-[18px]" aria-hidden="true">delete</span>
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="font-sans text-meta text-on-surface-variant py-2">
              No additional family members configured.
            </div>
          </div>
        </section>

        <!-- Career & Income Parameters -->
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <h2 class="font-sans text-heading font-semibold text-on-surface border-b border-outline-variant pb-3">
            Career &amp; Income Parameters
          </h2>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Employment status</label>
              <select
                v-model="userProfile.employment_status"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                data-testid="select-employment-status"
              >
                <option value="employed">Employed (Full-Time / Part-Time)</option>
                <option value="self_employed">Self-Employed / Business Owner</option>
                <option value="retired">Retired</option>
                <option value="student">Student</option>
                <option value="unemployed">Unemployed</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Occupation / title</label>
              <input
                v-model="userProfile.occupation"
                type="text"
                placeholder="e.g. Staff Systems Engineer"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                data-testid="input-occupation"
              />
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Gross annual income (USD)</label>
              <div class="relative">
                <span class="absolute left-3.5 top-2 text-on-surface-variant font-sans text-body">$</span>
                <input
                  v-model.number="userProfile.annual_income_usd"
                  type="number"
                  min="0"
                  step="1000"
                  placeholder="220000"
                  class="w-full pl-8 pr-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                  data-testid="input-annual-income"
                />
              </div>
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Monthly housing payment (USD)</label>
              <div class="relative">
                <span class="absolute left-3.5 top-2 text-on-surface-variant font-sans text-body">$</span>
                <input
                  v-model.number="userProfile.monthly_housing_payment_usd"
                  type="number"
                  min="0"
                  step="100"
                  placeholder="4200"
                  class="w-full pl-8 pr-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                  data-testid="input-housing-payment"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- TAB 2: Financial Goals & Timeline -->
      <div v-show="activeTab === 'goals'" class="flex flex-col gap-lg" data-testid="section-goals">
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant pb-3 gap-md">
            <h2 class="font-sans text-heading font-semibold text-on-surface">Financial Objectives &amp; Capital Goals</h2>
            <button
              type="button"
              class="px-3 py-1.5 font-sans text-meta font-medium text-primary hover:bg-surface-container-low rounded-md border border-outline-variant inline-flex items-center gap-1 transition-colors duration-150 ease-desk"
              data-testid="btn-add-goal"
              @click="addGoal"
            >
              <span class="material-symbols-outlined text-[16px]" aria-hidden="true">add</span>
              Add goal
            </button>
          </div>

          <div class="divide-y divide-outline-variant">
            <div
              v-for="(g, idx) in goals"
              :key="idx"
              class="py-md first:pt-0 flex flex-col gap-3"
              data-testid="goal-item-row"
            >
              <div class="flex items-center justify-between">
                <span class="font-sans text-meta font-semibold text-on-surface">
                  {{ idx === 0 ? 'Primary goal (IPS anchor)' : `Secondary goal #${idx + 1}` }}
                </span>
                <button
                  v-if="goals.length > 1"
                  type="button"
                  class="text-on-surface-variant hover:text-error font-sans text-meta inline-flex items-center gap-1 transition-colors duration-150 ease-desk"
                  data-testid="btn-remove-goal"
                  @click="removeGoal(idx)"
                >
                  <span class="material-symbols-outlined text-[16px]" aria-hidden="true">delete</span>
                  <span>Remove</span>
                </button>
              </div>

              <div class="flex flex-col gap-1.5">
                <label class="font-sans text-meta font-medium text-on-surface-variant">Goal description</label>
                <input
                  v-model="g.name"
                  type="text"
                  placeholder="e.g. Retirement Compounding & Financial Independence"
                  class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                  data-testid="input-goal-title"
                />
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Target amount (USD)</label>
                  <div class="relative">
                    <span class="absolute left-3.5 top-2 text-on-surface-variant font-sans text-body">$</span>
                    <input
                      v-model.number="g.target_amount_usd"
                      type="number"
                      min="0"
                      step="1000"
                      class="w-full pl-8 pr-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                      data-testid="input-goal-target-amount"
                    />
                  </div>
                </div>

                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Target date</label>
                  <input
                    v-model="g.target_date"
                    type="date"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                    data-testid="input-goal-target-date"
                  />
                </div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md pt-md border-t border-outline-variant">
            <div class="flex flex-col gap-1.5">
              <div class="flex justify-between items-baseline">
                <label class="font-sans text-meta font-medium text-on-surface-variant">Time horizon</label>
                <span class="font-sans text-body font-semibold text-on-surface tabular-nums" data-testid="val-time-horizon">
                  {{ timeHorizonYears }} years
                </span>
              </div>
              <input
                v-model.number="timeHorizonYears"
                type="range"
                min="1"
                max="40"
                class="w-full h-2 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary mt-2"
                data-testid="slider-time-horizon"
              />
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Target retirement age</label>
              <input
                v-model.number="targetRetirementAge"
                type="number"
                min="30"
                max="100"
                placeholder="62"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-target-retirement-age"
              />
            </div>

            <div class="flex flex-col gap-1.5 md:col-span-2">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Known near-term capital outlays (USD)</label>
              <div class="relative">
                <span class="absolute left-3.5 top-2 text-on-surface-variant font-sans text-body">$</span>
                <input
                  v-model.number="upcomingExpenses"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="w-full pl-8 pr-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                  data-testid="input-upcoming-expenses"
                />
              </div>
              <span class="font-sans text-meta text-on-surface-variant">
                Anticipated capital needs in the next 12 months (tuition, home renovations).
              </span>
            </div>

            <div class="flex flex-col gap-1.5 md:col-span-2">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Long-term milestones and family notes</label>
              <textarea
                v-model="financialGoalsNotes"
                rows="2"
                placeholder="Describe your qualitative goals and family milestones..."
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body resize-none focus:bg-surface-container-lowest"
                data-testid="textarea-goals-notes"
              ></textarea>
            </div>
          </div>
        </section>
      </div>

      <!-- TAB 3: Risk Calibration & Allocation -->
      <div v-show="activeTab === 'risk'" class="flex flex-col gap-lg" data-testid="section-risk">
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <h2 class="font-sans text-heading font-semibold text-on-surface border-b border-outline-variant pb-3">
            Risk Calibration &amp; Target Allocation Bands
          </h2>

          <!-- Drawdown Reaction Selector -->
          <div class="flex flex-col gap-2">
            <label class="font-sans text-meta font-medium text-on-surface-variant">
              Reaction to a sudden 20% market drawdown
            </label>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <button
                v-for="opt in reactionOptions"
                :key="opt.id"
                type="button"
                class="p-md rounded-lg border text-left flex flex-col gap-1.5 transition-[border-color,background-color] duration-150 ease-desk"
                :class="[
                  drawdownReaction === opt.id
                    ? 'border-primary bg-surface-container-low/70'
                    : 'border-outline-variant bg-surface-container-lowest hover:border-primary/50'
                ]"
                :data-testid="`reaction-opt-${opt.id}`"
                @click="onReactionSelect(opt.id)"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-sans text-body font-semibold text-on-surface">{{ opt.title }}</span>
                  <span
                    class="w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0"
                    :class="drawdownReaction === opt.id ? 'border-primary' : 'border-outline'"
                  >
                    <span
                      v-if="drawdownReaction === opt.id"
                      class="w-2 h-2 rounded-full bg-primary"
                    ></span>
                  </span>
                </div>
                <span class="font-sans text-meta text-on-surface-variant">{{ opt.description }}</span>
              </button>
            </div>
          </div>

          <!-- Derived Tier Bar -->
          <div class="flex items-center justify-between gap-md py-3 border-y border-outline-variant flex-wrap">
            <div class="flex items-baseline gap-2">
              <span class="font-sans text-meta text-on-surface-variant">Calibrated risk tier:</span>
              <span class="font-sans text-body capitalize font-semibold text-on-surface" data-testid="derived-risk-tier">
                {{ riskTolerance }}
              </span>
            </div>
            <select
              v-model="riskTolerance"
              class="px-3 py-1.5 font-sans text-meta font-medium rounded-md bg-surface border border-outline-variant text-on-surface"
              data-testid="select-risk-tier"
            >
              <option value="conservative">Conservative</option>
              <option value="moderate">Moderate</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </div>

          <!-- Allocation Visual & Controls -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-lg items-center pt-2">
            <div class="lg:col-span-5 flex flex-col items-center justify-center p-md bg-surface rounded-lg border border-outline-variant/80">
              <div class="relative w-36 h-36 flex items-center justify-center">
                <svg aria-label="Asset Allocation Chart" class="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle
                    v-for="(arc, idx) in chartArcs"
                    :key="idx"
                    cx="50"
                    cy="50"
                    r="40"
                    fill="transparent"
                    :stroke="arc.color"
                    stroke-width="11"
                    :stroke-dasharray="`${arc.len} 251.2`"
                    :stroke-dashoffset="arc.offset"
                    class="transition-[stroke-dasharray,stroke-dashoffset] duration-300 ease-desk"
                  ></circle>
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span class="font-sans text-heading font-semibold text-on-surface tabular-nums" data-testid="total-percent-display">
                    {{ totalTargetPercent }}%
                  </span>
                  <span class="font-sans text-meta text-on-surface-variant">Target</span>
                </div>
              </div>
              <div class="mt-3 flex items-baseline gap-2 font-sans text-meta">
                <span class="text-on-surface-variant">Projected return:</span>
                <span class="font-semibold text-on-surface tabular-nums" data-testid="projected-return">{{ projectedReturn }}</span>
              </div>
            </div>

            <div class="lg:col-span-7 divide-y divide-outline-variant/70">
              <div
                v-for="(band, idx) in bands"
                :key="band.asset_class"
                class="py-3 first:pt-0 last:pb-0 flex flex-col gap-2"
                data-testid="band-row"
              >
                <div class="flex justify-between items-center gap-md">
                  <span class="font-sans text-body font-medium text-on-surface">{{ band.asset_class }}</span>
                  <div class="flex items-center gap-1.5 tabular-nums">
                    <input
                      v-model.number="band.target_percent"
                      type="number"
                      min="0"
                      max="100"
                      class="w-16 text-center bg-surface py-1 rounded-md border border-outline-variant font-sans text-body text-on-surface"
                      :data-testid="`input-target-${idx}`"
                    />
                    <span class="font-sans text-meta text-on-surface-variant">%</span>
                  </div>
                </div>

                <input
                  v-model.number="band.target_percent"
                  type="range"
                  min="0"
                  max="100"
                  class="w-full h-1.5 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
                  :data-testid="`slider-target-${idx}`"
                />

                <div class="flex items-center justify-between font-sans text-meta text-on-surface-variant tabular-nums">
                  <span>Drift bounds</span>
                  <div class="flex items-center gap-1.5">
                    <span>Min</span>
                    <input
                      v-model.number="band.min_percent"
                      type="number"
                      min="0"
                      max="100"
                      class="w-14 text-center bg-surface py-0.5 rounded border border-outline-variant text-meta text-on-surface"
                      :data-testid="`input-min-${idx}`"
                    />
                    <span>% to Max</span>
                    <input
                      v-model.number="band.max_percent"
                      type="number"
                      min="0"
                      max="100"
                      class="w-14 text-center bg-surface py-0.5 rounded border border-outline-variant text-meta text-on-surface"
                      :data-testid="`input-max-${idx}`"
                    />
                    <span>%</span>
                  </div>
                </div>
              </div>

              <div
                v-if="totalTargetPercent !== 100"
                class="mt-3 p-3 rounded-md bg-secondary-fixed border border-secondary-fixed-dim text-on-secondary-fixed font-sans text-meta font-medium flex items-center gap-2"
                data-testid="allocation-warning"
              >
                <span class="material-symbols-outlined text-[18px]" aria-hidden="true">warning</span>
                <span>Total allocation must equal 100% (currently {{ totalTargetPercent }}%).</span>
              </div>
            </div>
          </div>

          <div class="flex flex-col gap-1.5 pt-md border-t border-outline-variant">
            <label class="font-sans text-meta font-medium text-on-surface-variant">
              Volatility comfort and drawdown notes
            </label>
            <textarea
              v-model="riskToleranceNotes"
              rows="2"
              placeholder="Describe your comfort with market volatility and drawdown scenarios..."
              class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body resize-none focus:bg-surface-container-lowest"
              data-testid="textarea-risk-notes"
            ></textarea>
          </div>
        </section>
      </div>

      <!-- TAB 4: Liabilities & Debt -->
      <div v-show="activeTab === 'liabilities'" class="flex flex-col gap-lg" data-testid="section-liabilities">
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant pb-3 gap-md">
            <h2 class="font-sans text-heading font-semibold text-on-surface">Current Liabilities &amp; Outstanding Debt</h2>
            <button
              v-if="!hasNoDebt"
              type="button"
              class="px-3 py-1.5 font-sans text-meta font-medium text-primary hover:bg-surface-container-low rounded-md border border-outline-variant inline-flex items-center gap-1 transition-colors duration-150 ease-desk"
              data-testid="btn-add-liability"
              @click="addLiability"
            >
              <span class="material-symbols-outlined text-[16px]" aria-hidden="true">add</span>
              Add liability
            </button>
          </div>

          <label class="flex items-center justify-between gap-md py-2 cursor-pointer">
            <div>
              <span class="font-sans text-body font-semibold text-on-surface block">Zero outstanding debt</span>
              <span class="font-sans text-meta text-on-surface-variant">
                Check if you carry no loans, mortgages, or credit card balances.
              </span>
            </div>
            <input
              v-model="hasNoDebt"
              type="checkbox"
              class="w-5 h-5 accent-primary cursor-pointer shrink-0"
              data-testid="toggle-no-debt"
            />
          </label>

          <div v-if="!hasNoDebt" class="divide-y divide-outline-variant border-t border-outline-variant">
            <div
              v-for="(item, idx) in liabilities"
              :key="item.liability_id || idx"
              class="py-md flex flex-col gap-3"
              data-testid="liability-item-row"
            >
              <div class="flex items-center justify-between">
                <span class="font-sans text-meta font-semibold text-on-surface">Liability #{{ idx + 1 }}</span>
                <button
                  type="button"
                  class="text-on-surface-variant hover:text-error font-sans text-meta inline-flex items-center gap-1 transition-colors duration-150 ease-desk"
                  data-testid="btn-remove-liability"
                  @click="removeLiability(idx)"
                >
                  <span class="material-symbols-outlined text-[16px]" aria-hidden="true">delete</span>
                  <span>Remove</span>
                </button>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Description</label>
                  <input
                    v-model="item.description"
                    type="text"
                    placeholder="e.g. Premium Rewards Card, Mortgage"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                    data-testid="input-liability-desc"
                  />
                </div>

                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Category</label>
                  <select
                    v-model="item.type"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                    data-testid="select-liability-type"
                  >
                    <option value="credit_card">Credit Card</option>
                    <option value="mortgage">Mortgage</option>
                    <option value="auto_loan">Auto Loan</option>
                    <option value="student_loan">Student Loan</option>
                    <option value="heloc">HELOC</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-md">
                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Balance (USD)</label>
                  <input
                    v-model.number="item.balance_usd"
                    type="number"
                    min="0"
                    placeholder="0"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                    data-testid="input-liability-balance"
                  />
                </div>

                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Interest APR (%)</label>
                  <input
                    v-model.number="item.interest_rate_percent"
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    placeholder="0"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                    data-testid="input-liability-apr"
                  />
                </div>

                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Min monthly payment (USD)</label>
                  <input
                    v-model.number="item.minimum_payment_usd"
                    type="number"
                    min="0"
                    placeholder="0"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                    data-testid="input-liability-min-payment"
                  />
                </div>
              </div>

              <div
                v-if="item.interest_rate_percent >= 15"
                class="p-3 rounded-md bg-secondary-fixed/70 border border-secondary-fixed-dim text-on-secondary-fixed font-sans text-meta flex items-center gap-2"
              >
                <span class="material-symbols-outlined text-[18px] shrink-0" aria-hidden="true">warning</span>
                <span>
                  High-interest debt ({{ item.interest_rate_percent }}% APR) is flagged for debt-paydown prioritization before aggressive equity allocation.
                </span>
              </div>
            </div>
          </div>

          <div class="flex justify-between items-center pt-3 border-t border-outline-variant font-sans text-body tabular-nums">
            <span class="text-on-surface-variant">Total reported liabilities</span>
            <span class="font-semibold text-on-surface" data-testid="total-liabilities-display">
              ${{ totalLiabilities.toLocaleString() }}
            </span>
          </div>
        </section>
      </div>

      <!-- TAB 5: Policy Guardrails & Constraints -->
      <div v-show="activeTab === 'policy'" class="flex flex-col gap-lg" data-testid="section-policy">
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <h2 class="font-sans text-heading font-semibold text-on-surface border-b border-outline-variant pb-3">
            Policy Guardrails &amp; HITL Sign-offs
          </h2>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Emergency reserve (months)</label>
              <input
                v-model.number="reserveMonths"
                type="number"
                min="1"
                max="36"
                placeholder="6"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-reserve-months"
              />
              <span class="font-sans text-meta text-on-surface-variant">Recommended: 3 to 6 months of living expenses.</span>
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Max single-stock concentration (%)</label>
              <input
                v-model.number="concentrationLimit"
                type="number"
                min="1"
                max="50"
                placeholder="15"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-concentration-limit"
              />
              <span class="font-sans text-meta text-on-surface-variant">Default limit: 15% per holding.</span>
            </div>

            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Account type</label>
              <select
                v-model="accountType"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                data-testid="select-account-type"
              >
                <option value="taxable">Individual Taxable Brokerage</option>
                <option value="retirement">Retirement (IRA / Roth / 401k)</option>
              </select>
            </div>

            <div class="flex flex-col justify-center gap-1.5">
              <span class="font-sans text-meta font-medium text-on-surface-variant">Tax-loss harvesting</span>
              <label class="flex items-center gap-2.5 cursor-pointer py-1.5">
                <input
                  v-model="taxLossHarvesting"
                  type="checkbox"
                  class="w-5 h-5 accent-primary cursor-pointer"
                  data-testid="toggle-tax-loss"
                />
                <span class="font-sans text-body text-on-surface">Enable automated TLH scans</span>
              </label>
            </div>

            <div class="flex flex-col gap-1.5 md:col-span-2 pt-md border-t border-outline-variant">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Excluded tickers (comma-separated)</label>
              <input
                v-model="excludedTickersStr"
                type="text"
                placeholder="e.g. TSLA, XOM, BABA"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                data-testid="input-excluded-tickers"
              />
            </div>

            <div class="flex flex-col gap-1.5 md:col-span-2">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Excluded sectors (comma-separated)</label>
              <input
                v-model="excludedSectorsStr"
                type="text"
                placeholder="e.g. tobacco, defense, fossil_fuels"
                class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body focus:bg-surface-container-lowest"
                data-testid="input-excluded-sectors"
              />
            </div>

            <div class="flex flex-col gap-3 md:col-span-2 pt-md border-t border-outline-variant">
              <div>
                <h3 class="font-sans text-body font-semibold text-on-surface">Autonomous Trade Governance (HITL Thresholds)</h3>
                <p class="font-sans text-meta text-on-surface-variant">
                  Trades exceeding either threshold require explicit human approval before execution.
                </p>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Require approval above (USD)</label>
                  <input
                    v-model.number="approvalAboveUsd"
                    type="number"
                    min="0"
                    placeholder="1000"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                    data-testid="input-approval-usd"
                  />
                </div>
                <div class="flex flex-col gap-1.5">
                  <label class="font-sans text-meta font-medium text-on-surface-variant">Require approval above (% of portfolio)</label>
                  <input
                    v-model.number="approvalAbovePct"
                    type="number"
                    min="0.1"
                    max="100"
                    placeholder="5"
                    class="px-3.5 py-2 rounded-md bg-surface border border-outline-variant text-on-surface font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                    data-testid="input-approval-pct"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- TAB 6: Income & Tax Documents -->
      <div v-show="activeTab === 'income'" class="flex flex-col gap-lg" data-testid="section-income">
        <!-- W-2 Upload Sheet -->
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <div class="flex items-baseline justify-between border-b border-outline-variant pb-3 gap-md flex-wrap">
            <h2 class="font-sans text-heading font-semibold text-on-surface">IRS Form W-2 Statement Ingestion</h2>
            <span class="font-sans text-meta text-on-surface-variant">Google Cloud Document AI</span>
          </div>

          <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
            Upload your IRS Form W-2 in PDF, PNG, or JPG format (up to 10 MB). Document AI extracts gross compensation, withholdings, and Box 12 retirement deferrals while masking SSNs.
          </p>

          <div
            class="border-2 border-dashed rounded-lg p-lg flex flex-col items-center justify-center text-center cursor-pointer transition-[border-color,background-color] duration-200 ease-desk"
            :class="[
              isDraggingW2
                ? 'border-on-tertiary-container bg-tertiary-fixed/30'
                : 'border-outline-variant bg-surface/60 hover:border-primary/60 hover:bg-surface-container-low/60'
            ]"
            data-testid="w2-dropzone"
            @dragover.prevent="isDraggingW2 = true"
            @dragleave.prevent="isDraggingW2 = false"
            @drop.prevent="onW2FileDrop"
            @click="triggerW2FileInput"
          >
            <input
              ref="w2FileInput"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              class="hidden"
              data-testid="input-w2-file"
              @change="onW2FileSelected"
            />

            <div v-if="isUploadingW2" class="flex flex-col items-center gap-2 py-md">
              <span class="material-symbols-outlined text-primary-fixed text-[32px] animate-spin" aria-hidden="true">
                progress_activity
              </span>
              <span class="font-sans text-body font-medium text-on-surface">Parsing W-2 with Document AI...</span>
              <span class="font-sans text-meta text-on-surface-variant">Extracting Boxes 1 to 20 and verifying employer records</span>
            </div>

            <div v-else class="flex flex-col items-center gap-1.5 py-sm">
              <span class="material-symbols-outlined text-primary text-[32px]" aria-hidden="true">upload_file</span>
              <span class="font-sans text-body font-medium text-on-surface">
                Drop your W-2 here, or <span class="text-primary-fixed underline">browse files</span>
              </span>
              <span class="font-sans text-meta text-on-surface-variant">
                Supported formats: PDF, PNG, JPG (up to 10 MB)
              </span>
            </div>
          </div>

          <div
            v-if="w2UploadSuccess"
            class="px-3.5 py-2.5 rounded-md bg-tertiary-fixed/50 border border-tertiary-fixed-dim text-on-tertiary-fixed flex items-center justify-between gap-md font-sans text-meta"
            data-testid="w2-upload-success"
          >
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[18px]" aria-hidden="true">check_circle</span>
              <span>{{ w2UploadSuccess }}</span>
            </div>
            <button type="button" class="font-medium hover:underline shrink-0" @click="w2UploadSuccess = null">Dismiss</button>
          </div>

          <div
            v-if="w2UploadError"
            class="px-3.5 py-2.5 rounded-md bg-error-container border border-error/30 text-on-error-container flex items-center justify-between gap-md font-sans text-meta"
            data-testid="w2-upload-error"
          >
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[18px]" aria-hidden="true">error</span>
              <span>{{ w2UploadError }}</span>
            </div>
            <button type="button" class="font-medium hover:underline shrink-0" @click="w2UploadError = null">Dismiss</button>
          </div>
        </section>

        <!-- Verified Tax Statements -->
        <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant pb-3 gap-md">
            <h2 class="font-sans text-heading font-semibold text-on-surface">Verified Tax Statements History</h2>
            <button
              type="button"
              class="font-sans text-meta font-medium text-primary hover:bg-surface-container-low px-3 py-1.5 rounded-md inline-flex items-center gap-1.5 transition-colors duration-150 ease-desk"
              data-testid="btn-refresh-w2"
              @click="loadW2Documents"
            >
              <span class="material-symbols-outlined text-[16px]" aria-hidden="true">refresh</span>
              Refresh
            </button>
          </div>

          <div v-if="loadingW2" class="py-lg text-center font-sans text-body text-on-surface-variant">
            Loading verified statements...
          </div>

          <div v-else-if="w2Documents.length === 0" class="py-lg text-center font-sans text-body text-on-surface-variant">
            No W-2 statements uploaded yet. Upload a tax statement above to verify your income.
          </div>

          <div v-else class="divide-y divide-outline-variant">
            <article
              v-for="w2 in w2Documents"
              :key="w2.id"
              class="py-md first:pt-0 last:pb-0 flex flex-col gap-3"
              data-testid="w2-card"
            >
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-sm">
                <div class="flex flex-wrap items-baseline gap-2.5">
                  <span class="font-sans text-body font-semibold text-primary tabular-nums">
                    Tax Year {{ w2.tax_year }}
                  </span>
                  <span class="font-sans text-body font-medium text-on-surface">
                    {{ w2.employer?.name || 'Employer' }}
                  </span>
                  <span v-if="w2.employer?.ein" class="font-sans text-meta text-on-surface-variant tabular-nums">
                    EIN {{ w2.employer.ein }}
                  </span>
                </div>

                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    class="px-3 py-1.5 rounded-md bg-surface-container-lowest hover:bg-surface-container-low text-primary border border-outline-variant font-sans text-meta font-medium transition-colors duration-150 ease-desk inline-flex items-center gap-1.5"
                    data-testid="btn-apply-w2"
                    :disabled="applyingW2Id === w2.id"
                    @click="handleApplyW2(w2)"
                  >
                    <span class="material-symbols-outlined text-[16px]" aria-hidden="true">sync_alt</span>
                    {{ applyingW2Id === w2.id ? 'Applying...' : 'Apply to Profile Income' }}
                  </button>

                  <button
                    type="button"
                    class="p-1.5 rounded-md text-on-surface-variant hover:text-error hover:bg-error-container/40 transition-colors duration-150 ease-desk"
                    title="Delete W-2"
                    data-testid="btn-delete-w2"
                    @click="handleDeleteW2(w2.id)"
                  >
                    <span class="material-symbols-outlined text-[18px]" aria-hidden="true">delete</span>
                  </button>
                </div>
              </div>

              <div class="grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-outline-variant rounded-md border border-outline-variant bg-surface/60 tabular-nums">
                <div class="p-3 flex flex-col gap-0.5">
                  <span class="font-sans text-meta text-on-surface-variant">Box 1: Wages</span>
                  <span class="font-sans text-body font-semibold text-on-surface" data-testid="w2-box1-wages">
                    ${{ (w2.wages_and_compensation?.box1_wages_tips_other_comp_usd ?? 0).toLocaleString() }}
                  </span>
                </div>
                <div class="p-3 flex flex-col gap-0.5">
                  <span class="font-sans text-meta text-on-surface-variant">Box 2: Federal tax</span>
                  <span class="font-sans text-body font-medium text-on-surface">
                    ${{ (w2.wages_and_compensation?.box2_federal_income_tax_withheld_usd ?? 0).toLocaleString() }}
                  </span>
                </div>
                <div class="p-3 flex flex-col gap-0.5">
                  <span class="font-sans text-meta text-on-surface-variant">Box 3: SS wages</span>
                  <span class="font-sans text-body font-medium text-on-surface">
                    ${{ (w2.wages_and_compensation?.box3_social_security_wages_usd ?? 0).toLocaleString() }}
                  </span>
                </div>
                <div class="p-3 flex flex-col gap-0.5">
                  <span class="font-sans text-meta text-on-surface-variant">Box 5: Medicare</span>
                  <span class="font-sans text-body font-medium text-on-surface">
                    ${{ (w2.wages_and_compensation?.box5_medicare_wages_and_tips_usd ?? 0).toLocaleString() }}
                  </span>
                </div>
              </div>

              <div v-if="w2.box12_items && w2.box12_items.length > 0" class="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-sans text-meta tabular-nums">
                <span class="font-medium text-on-surface-variant">Box 12 benefits:</span>
                <span v-for="(item, idx) in w2.box12_items" :key="idx" class="text-on-surface">
                  Code {{ item.code }}: ${{ item.amount_usd.toLocaleString() }}
                  <span v-if="item.description" class="text-on-surface-variant">({{ item.description }})</span>
                </span>
              </div>

              <div v-if="w2.state_taxes && w2.state_taxes.length > 0" class="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-sans text-meta tabular-nums">
                <span class="font-medium text-on-surface-variant">State taxes:</span>
                <span v-for="(st, sIdx) in w2.state_taxes" :key="sIdx" class="text-on-surface">
                  {{ st.state }}: Wages ${{ st.state_wages_usd.toLocaleString() }}, Tax ${{ st.state_income_tax_usd.toLocaleString() }}
                </span>
              </div>
            </article>
          </div>
        </section>
      </div>

      <!-- Action Footer -->
      <div class="flex items-center justify-between pt-md border-t border-outline-variant gap-md">
        <button
          type="button"
          class="px-4 py-2 font-sans text-body font-medium text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low rounded-md transition-colors duration-150 ease-desk"
          :disabled="isSaving"
          data-testid="btn-reset-profile"
          @click="resetAllForms"
        >
          Reset to Saved
        </button>

        <button
          type="submit"
          class="px-5 py-2.5 font-sans text-body font-medium bg-primary text-on-primary hover:bg-primary-container rounded-md transition-colors duration-150 ease-desk inline-flex items-center gap-2 disabled:opacity-50"
          :disabled="isSaving"
          data-testid="btn-save-profile"
          @click.prevent="handleSave"
        >
          <span v-if="isSaving" class="material-symbols-outlined animate-spin text-[18px]" aria-hidden="true">
            progress_activity
          </span>
          <span v-else class="material-symbols-outlined text-[18px]" aria-hidden="true">save</span>
          {{ isSaving ? 'Saving Profile & Policy...' : 'Save Profile & Policy' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import type {
  UserProfile,
  FamilyMember,
  Goal,
  LiabilityItem,
  RiskToleranceTier,
  DrawdownReaction,
  AllocationBand,
  OnboardingProfile,
  W2Document
} from '../types';
import { apiService } from '../services/api';
import { deriveRiskTolerance, getDefaultAllocationBands } from '../services/onboarding';

const router = useRouter();

interface ReactionOption {
  id: DrawdownReaction;
  title: string;
  description: string;
}

type TabId = 'personal' | 'goals' | 'risk' | 'liabilities' | 'policy' | 'income';

const activeTab = ref<TabId>('personal');
const isSaving = ref(false);
const saveSuccess = ref(false);
const saveError = ref<string | null>(null);

const hasActiveIPS = ref(false);
const ipsVersion = ref(1);

const tabs: { id: TabId; label: string; icon: string }[] = [
  { id: 'personal', label: 'Personal & Family', icon: 'person' },
  { id: 'goals', label: 'Goals & Timeline', icon: 'flag' },
  { id: 'risk', label: 'Risk & Allocation', icon: 'pie_chart' },
  { id: 'liabilities', label: 'Liabilities & Debt', icon: 'credit_card' },
  { id: 'policy', label: 'Policy Guardrails', icon: 'gavel' },
  { id: 'income', label: 'Income & Tax', icon: 'receipt_long' }
];

const userProfile = reactive<UserProfile>({
  user_id: 'demo_user',
  full_name: '',
  email: '',
  date_of_birth: '',
  age: undefined,
  marital_status: 'single',
  dependents_count: 0,
  family_members: [],
  employment_status: 'employed',
  occupation: '',
  annual_income_usd: undefined,
  target_retirement_age: undefined,
  monthly_housing_payment_usd: undefined,
  risk_tolerance_notes: '',
  financial_goals_notes: '',
  updated_at: ''
});

const goals = ref<Goal[]>([
  {
    name: 'Retirement Compounding & Financial Independence',
    target_amount_usd: 1500000,
    target_date: '2039-12-31'
  }
]);
const timeHorizonYears = ref(15);
const targetRetirementAge = ref<number | undefined>(62);
const upcomingExpenses = ref(0);
const financialGoalsNotes = ref('');

const drawdownReaction = ref<DrawdownReaction>('hold');
const riskTolerance = ref<RiskToleranceTier>('aggressive');
const bands = ref<AllocationBand[]>(getDefaultAllocationBands('aggressive'));
const riskToleranceNotes = ref('');

const reactionOptions: ReactionOption[] = [
  {
    id: 'buy_more',
    title: 'Buy More',
    description: 'Deploy reserve cash into depressed valuations to accelerate compounding.'
  },
  {
    id: 'hold',
    title: 'Hold Steady',
    description: 'Maintain policy weights and let long-term horizon compound returns.'
  },
  {
    id: 'sell',
    title: 'Sell to Capital Preservation',
    description: 'Liquidate equities to cash or treasuries to limit further portfolio drawdown.'
  }
];

const hasNoDebt = ref(false);
const liabilities = ref<LiabilityItem[]>([
  {
    liability_id: 'liab_001',
    type: 'credit_card',
    description: 'Premium Rewards Card',
    balance_usd: 4850,
    interest_rate_percent: 24.99,
    minimum_payment_usd: 150
  }
]);

const reserveMonths = ref(6);
const concentrationLimit = ref(15);
const accountType = ref<'taxable' | 'retirement'>('taxable');
const taxLossHarvesting = ref(true);
const excludedTickersStr = ref('');
const excludedSectorsStr = ref('');
const approvalAboveUsd = ref(1000);
const approvalAbovePct = ref(5);

const initialProfileSnapshot = ref<UserProfile | null>(null);
const initialOnboardingSnapshot = ref<OnboardingProfile | null>(null);

const totalLiabilities = computed(() => {
  if (hasNoDebt.value) return 0;
  return liabilities.value.reduce((acc, l) => acc + (Number(l.balance_usd) || 0), 0);
});

const totalTargetPercent = computed(() => {
  return bands.value.reduce((sum, b) => sum + (Number(b.target_percent) || 0), 0);
});

const CIRCUMFERENCE = 251.2;
const arcColors = ['#0f2342', '#1e40af', '#047857', '#334e68', '#64748b'];

const chartArcs = computed(() => {
  let accumulatedOffset = 0;
  return bands.value.map((band, idx) => {
    const pct = Math.max(0, band.target_percent) / 100;
    const len = pct * CIRCUMFERENCE;
    const offset = -accumulatedOffset;
    accumulatedOffset += len;
    return {
      len,
      offset: `${offset}`,
      color: arcColors[idx % arcColors.length]
    };
  });
});

const projectedReturn = computed(() => {
  const eq = bands.value[0]?.target_percent || 0;
  const fi = bands.value[1]?.target_percent || 0;
  const cash = bands.value[2]?.target_percent || 0;
  const ret = (eq * 0.08) + (fi * 0.04) + (cash * 0.01);
  return ret.toFixed(1) + '%';
});

function calculateAgeFromDOB() {
  if (!userProfile.date_of_birth) return;
  const dob = new Date(userProfile.date_of_birth);
  if (isNaN(dob.getTime())) return;
  const today = new Date();
  let calculatedAge = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    calculatedAge--;
  }
  if (calculatedAge >= 0) {
    userProfile.age = calculatedAge;
  }
}

function addFamilyMember() {
  userProfile.family_members = userProfile.family_members || [];
  userProfile.family_members.push({
    name: '',
    relationship: 'child',
    age: 0
  });
}

function removeFamilyMember(index: number) {
  if (userProfile.family_members) {
    userProfile.family_members.splice(index, 1);
  }
}

function addGoal() {
  goals.value.push({
    name: '',
    target_amount_usd: 100000,
    target_date: '2035-01-01'
  });
}

function removeGoal(index: number) {
  if (goals.value.length > 1) {
    goals.value.splice(index, 1);
  }
}

function onReactionSelect(reaction: DrawdownReaction) {
  drawdownReaction.value = reaction;
  const derived = deriveRiskTolerance(timeHorizonYears.value, reaction);
  riskTolerance.value = derived;
  bands.value = getDefaultAllocationBands(derived);
}

function addLiability() {
  liabilities.value.push({
    liability_id: `liab_${Date.now()}`,
    type: 'other',
    description: '',
    balance_usd: 0,
    interest_rate_percent: 0,
    minimum_payment_usd: 0
  });
}

function removeLiability(index: number) {
  liabilities.value.splice(index, 1);
  if (liabilities.value.length === 0) {
    hasNoDebt.value = true;
  }
}

function populateUserProfile(profile: UserProfile) {
  userProfile.user_id = profile.user_id || 'demo_user';
  userProfile.full_name = profile.full_name || '';
  userProfile.email = profile.email || '';
  userProfile.date_of_birth = profile.date_of_birth || '';
  userProfile.age = profile.age;
  userProfile.marital_status = profile.marital_status || 'single';
  userProfile.dependents_count = profile.dependents_count ?? 0;
  userProfile.family_members = (profile.family_members || []).map((m: FamilyMember) => ({ ...m }));
  userProfile.employment_status = profile.employment_status || 'employed';
  userProfile.occupation = profile.occupation || '';
  userProfile.annual_income_usd = profile.annual_income_usd;
  userProfile.target_retirement_age = profile.target_retirement_age;
  userProfile.monthly_housing_payment_usd = profile.monthly_housing_payment_usd;
  userProfile.risk_tolerance_notes = profile.risk_tolerance_notes || '';
  userProfile.financial_goals_notes = profile.financial_goals_notes || '';
  userProfile.updated_at = profile.updated_at || '';

  if (profile.target_retirement_age) {
    targetRetirementAge.value = profile.target_retirement_age;
  }
  if (profile.financial_goals_notes) {
    financialGoalsNotes.value = profile.financial_goals_notes;
  }
  if (profile.risk_tolerance_notes) {
    riskToleranceNotes.value = profile.risk_tolerance_notes;
  }
}

function populateOnboardingProfile(profile: OnboardingProfile) {
  if (profile.has_active_ips) {
    hasActiveIPS.value = true;
    if (profile.version) {
      ipsVersion.value = profile.version;
    }
    if (profile.goals && profile.goals.length > 0) {
      goals.value = JSON.parse(JSON.stringify(profile.goals));
    }
    if (profile.time_horizon_years) {
      timeHorizonYears.value = profile.time_horizon_years;
    }
    if (profile.known_upcoming_expenses_usd !== undefined) {
      upcomingExpenses.value = profile.known_upcoming_expenses_usd;
    }
    if (profile.reserve_months !== undefined) {
      reserveMonths.value = profile.reserve_months;
    }
    if (profile.risk_tolerance) {
      riskTolerance.value = profile.risk_tolerance;
    }
    if (profile.target_bands && profile.target_bands.length > 0) {
      bands.value = JSON.parse(JSON.stringify(profile.target_bands));
    }
    if (profile.constraints) {
      concentrationLimit.value = profile.constraints.concentration_limit_percent ?? 15;
      accountType.value = profile.constraints.account_type ?? 'taxable';
      taxLossHarvesting.value = profile.constraints.tax_loss_harvesting_enabled ?? true;
      excludedTickersStr.value = (profile.constraints.excluded_tickers || []).join(', ');
      excludedSectorsStr.value = (profile.constraints.excluded_sectors || []).join(', ');
    }
    if (profile.approval_required_above_usd !== undefined) {
      approvalAboveUsd.value = profile.approval_required_above_usd;
    }
    if (profile.approval_required_above_percent !== undefined) {
      approvalAbovePct.value = profile.approval_required_above_percent;
    }
    if (profile.liabilities) {
      if (profile.liabilities.length === 0) {
        hasNoDebt.value = true;
        liabilities.value = [];
      } else {
        hasNoDebt.value = false;
        liabilities.value = JSON.parse(JSON.stringify(profile.liabilities));
      }
    }
  }
}

function resetAllForms() {
  if (initialProfileSnapshot.value) {
    populateUserProfile(initialProfileSnapshot.value);
  }
  if (initialOnboardingSnapshot.value) {
    populateOnboardingProfile(initialOnboardingSnapshot.value);
  }
}

async function loadData() {
  try {
    const [profileData, onboardingData] = await Promise.all([
      apiService.getUserProfile('demo_user').catch(() => null),
      apiService.getOnboarding('demo_user').catch(() => null)
    ]);

    if (profileData) {
      initialProfileSnapshot.value = JSON.parse(JSON.stringify(profileData));
      populateUserProfile(profileData);
    }
    if (onboardingData) {
      initialOnboardingSnapshot.value = JSON.parse(JSON.stringify(onboardingData));
      populateOnboardingProfile(onboardingData);
    }
    await loadW2Documents();
  } catch {
    saveError.value = 'Failed to load initial settings.';
  }
}

const w2Documents = ref<W2Document[]>([]);
const loadingW2 = ref(false);
const isUploadingW2 = ref(false);
const isDraggingW2 = ref(false);
const w2UploadSuccess = ref<string | null>(null);
const w2UploadError = ref<string | null>(null);
const applyingW2Id = ref<string | null>(null);
const w2FileInput = ref<HTMLInputElement | null>(null);

function triggerW2FileInput() {
  if (w2FileInput.value) {
    w2FileInput.value.click();
  }
}

async function loadW2Documents() {
  loadingW2.value = true;
  try {
    const list = await apiService.getW2Documents(userProfile.user_id || 'demo_user');
    w2Documents.value = list || [];
  } catch (err: any) {
    w2UploadError.value = err?.message || 'Failed to load W-2 documents';
  } finally {
    loadingW2.value = false;
  }
}

async function uploadW2File(file: File) {
  isUploadingW2.value = true;
  w2UploadError.value = null;
  w2UploadSuccess.value = null;

  try {
    const doc = await apiService.uploadW2(file, userProfile.user_id || 'demo_user');
    w2UploadSuccess.value = `Parsed Form W-2 (${doc.tax_year}) for ${doc.employer?.name || 'employer'}. Box 1 Wages: $${doc.wages_and_compensation.box1_wages_tips_other_comp_usd.toLocaleString()}`;
    await loadW2Documents();
  } catch (err: any) {
    w2UploadError.value = err?.message || 'Failed to upload and parse W-2';
  } finally {
    isUploadingW2.value = false;
  }
}

function onW2FileSelected(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const file = target.files[0];
    uploadW2File(file);
    target.value = '';
  }
}

function onW2FileDrop(event: DragEvent) {
  isDraggingW2.value = false;
  if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length > 0) {
    const file = event.dataTransfer.files[0];
    uploadW2File(file);
  }
}

async function handleApplyW2(doc: W2Document) {
  applyingW2Id.value = doc.id;
  w2UploadError.value = null;
  w2UploadSuccess.value = null;

  try {
    const res = await apiService.applyW2ToProfile(doc.id, userProfile.user_id || 'demo_user');
    if (res?.profile) {
      userProfile.annual_income_usd = res.profile.annual_income_usd;
      if (res.profile.occupation) {
        userProfile.occupation = res.profile.occupation;
      }
      w2UploadSuccess.value = `Successfully synchronized Box 1 wages ($${doc.wages_and_compensation.box1_wages_tips_other_comp_usd.toLocaleString()}) to Profile Annual Income.`;
    }
  } catch (err: any) {
    w2UploadError.value = err?.message || 'Failed to apply W-2 income to profile';
  } finally {
    applyingW2Id.value = null;
  }
}

async function handleDeleteW2(id: string) {
  if (!confirm('Are you sure you want to delete this W-2 tax statement?')) {
    return;
  }
  try {
    await apiService.deleteW2Document(id, userProfile.user_id || 'demo_user');
    w2UploadSuccess.value = 'W-2 statement deleted successfully.';
    await loadW2Documents();
  } catch (err: any) {
    w2UploadError.value = err?.message || 'Failed to delete W-2 statement';
  }
}

async function handleSave() {
  isSaving.value = true;
  saveSuccess.value = false;
  saveError.value = null;

  try {
    const profilePayload: UserProfile = {
      ...userProfile,
      user_id: userProfile.user_id || 'demo_user',
      financial_goals_notes: financialGoalsNotes.value,
      risk_tolerance_notes: riskToleranceNotes.value,
      target_retirement_age: targetRetirementAge.value,
      updated_at: new Date().toISOString()
    };
    const profileRes = await apiService.updateUserProfile(profilePayload);
    if (profileRes?.profile) {
      initialProfileSnapshot.value = JSON.parse(JSON.stringify(profileRes.profile));
      populateUserProfile(profileRes.profile);
    }

    const [primaryGoal, ...additionalGoals] = goals.value;
    const ipsResult: Record<string, unknown> = {
      user_id: userProfile.user_id || 'demo_user',
      primary_goal: primaryGoal ?? {
        name: 'Retirement Compounding & Growth',
        target_amount_usd: 1500000,
        target_date: '2039-12-31'
      },
      additional_goals: additionalGoals ?? [],
      risk_tolerance: riskTolerance.value,
      time_horizon_years: timeHorizonYears.value,
      target_allocation: bands.value,
      constraints: {
        excluded_tickers: excludedTickersStr.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean),
        excluded_sectors: excludedSectorsStr.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean),
        concentration_limit_percent: Number(concentrationLimit.value) || 15,
        tax_loss_harvesting_enabled: taxLossHarvesting.value,
        account_type: accountType.value
      },
      liquidity_needs: {
        reserve_months: Number(reserveMonths.value) || 6,
        known_upcoming_expenses_usd: Number(upcomingExpenses.value) || 0
      },
      identified_liabilities: hasNoDebt.value
        ? []
        : liabilities.value.map(l => ({
            liability_id: l.liability_id || `liab_${Date.now()}`,
            type: l.type,
            description: l.description,
            balance_usd: Number(l.balance_usd) || 0,
            interest_rate_percent: Number(l.interest_rate_percent) || 0,
            minimum_payment_usd: Number(l.minimum_payment_usd) || 0
          })),
      interview_summary: `Profile & Policy settings update: ${riskTolerance.value} risk, ${timeHorizonYears.value}y horizon, ${hasNoDebt.value ? 0 : liabilities.value.length} liabilities.`
    };

    const onboardingRes = await apiService.applyOnboarding({
      user_id: userProfile.user_id || 'demo_user',
      result: ipsResult,
      trigger: hasActiveIPS.value ? 'update' : 'initial',
      approval_required_above_usd: Number(approvalAboveUsd.value) || 1000,
      approval_required_above_percent: Number(approvalAbovePct.value) || 5
    });

    if (onboardingRes?.version) {
      ipsVersion.value = onboardingRes.version;
      hasActiveIPS.value = true;
    }

    saveSuccess.value = true;
  } catch (err: any) {
    saveError.value = err?.message || 'Failed to save profile and policy settings. Please check your inputs.';
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  loadData();
});
</script>
