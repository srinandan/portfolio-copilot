<template>
  <div class="flex flex-col gap-lg w-full max-w-5xl mx-auto pb-xl" data-testid="profile-view">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-md border-b border-outline-variant/30 pb-md">
      <div class="flex flex-col gap-xs">
        <div class="flex items-center gap-xs text-primary font-label-caps text-label-caps uppercase tracking-wider">
          <span class="material-symbols-outlined text-[18px]">verified_user</span>
          Profile &amp; Governance Policy
        </div>
        <h1 class="font-headline-lg-mobile text-headline-lg-mobile text-on-background">User Profile &amp; Policy Settings</h1>
        <p class="font-body-base text-body-base text-on-surface-variant max-w-2xl">
          Unified management for personal context, financial goals, risk calibration, liabilities, and autonomous governance guardrails.
        </p>
      </div>

      <!-- Quick Action / Status Badges -->
      <div class="flex flex-wrap items-center gap-sm">
        <div
          class="px-sm py-1 rounded-full text-xs font-body-mono flex items-center gap-1 border shadow-xs"
          :class="[
            hasActiveIPS
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400'
          ]"
          data-testid="badge-ips-status"
        >
          <span class="material-symbols-outlined text-[14px]">
            {{ hasActiveIPS ? 'check_circle' : 'pending' }}
          </span>
          <span>{{ hasActiveIPS ? `Active IPS (v${ipsVersion})` : 'Draft Policy' }}</span>
        </div>

        <button
          type="button"
          @click="router.push('/onboarding')"
          class="px-md py-sm bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-xs font-medium rounded-md border border-outline-variant transition-colors flex items-center gap-xs shadow-xs"
          data-testid="btn-launch-wizard"
        >
          <span class="material-symbols-outlined text-primary text-[16px]">auto_awesome</span>
          Run Guided Setup
        </button>
      </div>
    </div>

    <!-- Alert / Status Banners -->
    <div
      v-if="saveSuccess"
      class="p-md rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 flex items-center justify-between shadow-xs"
      data-testid="profile-save-success"
    >
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-emerald-600 text-[20px]">check_circle</span>
        <span class="font-medium text-sm">Profile and Investment Policy Statement successfully saved and synchronized.</span>
      </div>
      <button class="text-xs text-emerald-600 hover:underline" @click="saveSuccess = false">Dismiss</button>
    </div>

    <div
      v-if="saveError"
      class="p-md rounded-md bg-red-500/10 border border-red-500/30 text-red-600 flex items-center justify-between shadow-xs"
      data-testid="profile-save-error"
    >
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-red-600 text-[20px]">error</span>
        <span class="font-medium text-sm">{{ saveError }}</span>
      </div>
      <button class="text-xs text-red-600 hover:underline" @click="saveError = null">Dismiss</button>
    </div>

    <!-- Metric Summary Bar -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-sm">
      <div class="bg-surface-container rounded-lg p-sm border border-outline-variant/40 flex flex-col gap-0.5">
        <span class="font-label-caps text-[10px] text-on-surface-variant uppercase">Risk Tolerance</span>
        <span class="font-title-sm text-sm capitalize font-bold text-on-surface" data-testid="metric-risk-tolerance">
          {{ riskTolerance }}
        </span>
      </div>
      <div class="bg-surface-container rounded-lg p-sm border border-outline-variant/40 flex flex-col gap-0.5">
        <span class="font-label-caps text-[10px] text-on-surface-variant uppercase">Planning Horizon</span>
        <span class="font-title-sm text-sm font-mono text-on-surface" data-testid="metric-time-horizon">
          {{ timeHorizonYears }} Years
        </span>
      </div>
      <div class="bg-surface-container rounded-lg p-sm border border-outline-variant/40 flex flex-col gap-0.5">
        <span class="font-label-caps text-[10px] text-on-surface-variant uppercase">Reported Liabilities</span>
        <span class="font-title-sm text-sm font-mono text-on-surface" data-testid="metric-total-liabilities">
          ${{ totalLiabilities.toLocaleString() }}
        </span>
      </div>
      <div class="bg-surface-container rounded-lg p-sm border border-outline-variant/40 flex flex-col gap-0.5">
        <span class="font-label-caps text-[10px] text-on-surface-variant uppercase">Concentration Limit</span>
        <span class="font-title-sm text-sm font-mono text-on-surface" data-testid="metric-concentration-limit">
          {{ concentrationLimit }}% Max / Ticker
        </span>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="flex items-center gap-xs border-b border-outline-variant/40 overflow-x-auto pb-1" data-testid="profile-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="px-md py-sm font-body-base text-sm rounded-md transition-colors flex items-center gap-xs whitespace-nowrap"
        :class="[
          activeTab === tab.id
            ? 'bg-primary-container text-on-primary font-medium shadow-xs'
            : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
        ]"
        :data-testid="`tab-${tab.id}`"
        @click="activeTab = tab.id"
      >
        <span class="material-symbols-outlined text-[18px]">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- Main Settings Form -->
    <form @submit.prevent="handleSave" class="flex flex-col gap-lg">
      <!-- TAB 1: Personal & Family Information -->
      <div v-show="activeTab === 'personal'" class="flex flex-col gap-lg" data-testid="section-personal">
        <!-- Personal Details -->
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center gap-sm border-b border-outline-variant/30 pb-sm">
            <span class="material-symbols-outlined text-primary text-[20px]">person</span>
            <h2 class="font-title-sm text-on-surface font-semibold">Personal Demographics</h2>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Full Name</label>
              <input
                v-model="userProfile.full_name"
                type="text"
                placeholder="e.g. Alex Mercer"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
                data-testid="input-full-name"
              />
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Email Address</label>
              <input
                v-model="userProfile.email"
                type="email"
                placeholder="e.g. alex.mercer@example.com"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
                data-testid="input-email"
              />
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Date of Birth</label>
              <input
                v-model="userProfile.date_of_birth"
                type="date"
                @change="calculateAgeFromDOB"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
                data-testid="input-dob"
              />
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Age</label>
              <input
                v-model.number="userProfile.age"
                type="number"
                min="0"
                max="150"
                placeholder="e.g. 46"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
                data-testid="input-age"
              />
            </div>

            <div class="flex flex-col gap-xs md:col-span-2">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Marital Status</label>
              <select
                v-model="userProfile.marital_status"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
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
        </div>

        <!-- Family & Dependents -->
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant/30 pb-sm">
            <div class="flex items-center gap-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">group</span>
              <h2 class="font-title-sm text-on-surface font-semibold">Family &amp; Dependents</h2>
            </div>
            <button
              type="button"
              @click="addFamilyMember"
              class="px-sm py-xs text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 rounded-md flex items-center gap-xs transition-colors"
              data-testid="btn-add-family-member"
            >
              <span class="material-symbols-outlined text-[16px]">add</span>
              Add Member
            </button>
          </div>

          <div class="flex flex-col gap-sm">
            <div class="flex items-center gap-md">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Number of Financial Dependents</label>
              <input
                v-model.number="userProfile.dependents_count"
                type="number"
                min="0"
                class="w-24 px-md py-xs rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
                data-testid="input-dependents-count"
              />
            </div>

            <!-- Family Members Table -->
            <div v-if="userProfile.family_members && userProfile.family_members.length > 0" class="flex flex-col gap-xs mt-sm">
              <div
                v-for="(member, idx) in userProfile.family_members"
                :key="idx"
                class="grid grid-cols-12 gap-sm items-center bg-surface p-sm rounded-md border border-outline-variant/30"
                data-testid="family-member-row"
              >
                <div class="col-span-5 flex flex-col gap-xs">
                  <span class="text-[10px] uppercase font-label-caps text-on-surface-variant">Name</span>
                  <input
                    v-model="member.name"
                    type="text"
                    placeholder="Name"
                    class="px-sm py-xs text-xs bg-surface-container border border-outline-variant rounded focus:outline-none focus:border-primary text-on-surface"
                  />
                </div>
                <div class="col-span-4 flex flex-col gap-xs">
                  <span class="text-[10px] uppercase font-label-caps text-on-surface-variant">Relationship</span>
                  <select
                    v-model="member.relationship"
                    class="px-sm py-xs text-xs bg-surface-container border border-outline-variant rounded focus:outline-none focus:border-primary text-on-surface"
                  >
                    <option value="spouse">Spouse</option>
                    <option value="child">Child</option>
                    <option value="parent">Parent</option>
                    <option value="sibling">Sibling</option>
                    <option value="dependent">Dependent</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div class="col-span-2 flex flex-col gap-xs">
                  <span class="text-[10px] uppercase font-label-caps text-on-surface-variant">Age</span>
                  <input
                    v-model.number="member.age"
                    type="number"
                    min="0"
                    max="150"
                    class="px-sm py-xs text-xs font-mono bg-surface-container border border-outline-variant rounded focus:outline-none focus:border-primary text-on-surface"
                  />
                </div>
                <div class="col-span-1 flex justify-end pt-3">
                  <button
                    type="button"
                    @click="removeFamilyMember(idx)"
                    class="text-on-surface-variant hover:text-red-500 p-1"
                    title="Remove family member"
                    data-testid="btn-remove-family-member"
                  >
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-xs text-on-surface-variant italic py-sm text-center">
              No additional family members configured.
            </div>
          </div>
        </div>

        <!-- Career & Financial Context -->
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center gap-sm border-b border-outline-variant/30 pb-sm">
            <span class="material-symbols-outlined text-primary text-[20px]">work</span>
            <h2 class="font-title-sm text-on-surface font-semibold">Career &amp; Income Parameters</h2>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Employment Status</label>
              <select
                v-model="userProfile.employment_status"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
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

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Occupation / Title</label>
              <input
                v-model="userProfile.occupation"
                type="text"
                placeholder="e.g. Staff Systems Engineer"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
                data-testid="input-occupation"
              />
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Gross Annual Income (USD)</label>
              <div class="relative">
                <span class="absolute left-3 top-2.5 text-on-surface-variant text-sm font-mono">$</span>
                <input
                  v-model.number="userProfile.annual_income_usd"
                  type="number"
                  min="0"
                  step="1000"
                  placeholder="220000"
                  class="w-full pl-7 pr-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
                  data-testid="input-annual-income"
                />
              </div>
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Monthly Housing Payment (USD)</label>
              <div class="relative">
                <span class="absolute left-3 top-2.5 text-on-surface-variant text-sm font-mono">$</span>
                <input
                  v-model.number="userProfile.monthly_housing_payment_usd"
                  type="number"
                  min="0"
                  step="100"
                  placeholder="4200"
                  class="w-full pl-7 pr-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
                  data-testid="input-housing-payment"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 2: Financial Goals & Timeline -->
      <div v-show="activeTab === 'goals'" class="flex flex-col gap-lg" data-testid="section-goals">
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant/30 pb-sm">
            <div class="flex items-center gap-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">flag</span>
              <h2 class="font-title-sm text-on-surface font-semibold">Financial Objectives &amp; Capital Goals</h2>
            </div>
            <button
              type="button"
              @click="addGoal"
              class="px-sm py-xs text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 rounded-md flex items-center gap-xs transition-colors"
              data-testid="btn-add-goal"
            >
              <span class="material-symbols-outlined text-[16px]">add</span>
              Add Goal
            </button>
          </div>

          <!-- Goals List -->
          <div class="flex flex-col gap-md">
            <div
              v-for="(g, idx) in goals"
              :key="idx"
              class="bg-surface p-md rounded-lg border border-outline-variant/40 flex flex-col gap-sm relative"
              data-testid="goal-item-row"
            >
              <div class="flex items-center justify-between border-b border-outline-variant/20 pb-xs">
                <span class="font-label-caps text-[11px] text-on-surface-variant uppercase font-medium">
                  {{ idx === 0 ? 'Primary Goal (IPS Anchor)' : `Secondary Goal #${idx + 1}` }}
                </span>
                <button
                  v-if="goals.length > 1"
                  type="button"
                  @click="removeGoal(idx)"
                  class="text-on-surface-variant hover:text-red-500 text-xs flex items-center gap-1"
                  data-testid="btn-remove-goal"
                >
                  <span class="material-symbols-outlined text-[16px]">delete</span>
                  <span>Remove</span>
                </button>
              </div>

              <div class="flex flex-col gap-xs">
                <label class="font-label-caps text-xs text-on-surface-variant uppercase">Goal Description / Title</label>
                <input
                  v-model="g.name"
                  type="text"
                  placeholder="e.g. Retirement Compounding & Financial Independence"
                  class="px-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface text-sm focus:outline-none focus:border-primary"
                  data-testid="input-goal-title"
                />
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Target Amount ($ USD)</label>
                  <div class="relative">
                    <span class="absolute left-3 top-2.5 text-on-surface-variant text-sm font-mono">$</span>
                    <input
                      v-model.number="g.target_amount_usd"
                      type="number"
                      min="0"
                      step="1000"
                      class="w-full pl-7 pr-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                      data-testid="input-goal-target-amount"
                    />
                  </div>
                </div>

                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Target Date</label>
                  <input
                    v-model="g.target_date"
                    type="date"
                    class="px-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                    data-testid="input-goal-target-date"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Timeline & Near-Term Liquidity -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-md pt-sm border-t border-outline-variant/30">
            <div class="flex flex-col gap-xs">
              <div class="flex justify-between items-center">
                <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Time Horizon (Years)</label>
                <span class="font-mono text-sm font-bold text-on-surface" data-testid="val-time-horizon">{{ timeHorizonYears }} years</span>
              </div>
              <input
                v-model.number="timeHorizonYears"
                type="range"
                min="1"
                max="40"
                class="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-primary mt-1"
                data-testid="slider-time-horizon"
              />
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Target Retirement Age</label>
              <input
                v-model.number="targetRetirementAge"
                type="number"
                min="30"
                max="100"
                placeholder="62"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
                data-testid="input-target-retirement-age"
              />
            </div>

            <div class="flex flex-col gap-xs md:col-span-2">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Known Near-Term Capital Outlays ($ USD)</label>
              <div class="relative">
                <span class="absolute left-3 top-2.5 text-on-surface-variant text-sm font-mono">$</span>
                <input
                  v-model.number="upcomingExpenses"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="w-full pl-7 pr-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
                  data-testid="input-upcoming-expenses"
                />
              </div>
              <span class="text-xs text-on-surface-variant">Anticipated capital needs in next 12 months (e.g. tuition, renovations).</span>
            </div>

            <div class="flex flex-col gap-xs md:col-span-2">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Long-Term Milestones &amp; Family Objectives (Notes)</label>
              <textarea
                v-model="financialGoalsNotes"
                rows="2"
                placeholder="Describe your qualitative goals and family milestones..."
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm resize-none"
                data-testid="textarea-goals-notes"
              ></textarea>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 3: Risk Calibration & Target Allocation Bands -->
      <div v-show="activeTab === 'risk'" class="flex flex-col gap-lg" data-testid="section-risk">
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center gap-sm border-b border-outline-variant/30 pb-sm">
            <span class="material-symbols-outlined text-primary text-[20px]">pie_chart</span>
            <h2 class="font-title-sm text-on-surface font-semibold">Risk Calibration &amp; Target Allocation Bands</h2>
          </div>

          <!-- Risk Reaction Options -->
          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">
              Market Drawdown Psychological Reaction (20% Drop)
            </label>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-sm mt-1">
              <button
                v-for="opt in reactionOptions"
                :key="opt.id"
                type="button"
                class="p-md rounded-lg border text-left flex flex-col gap-1 transition-all"
                :class="[
                  drawdownReaction === opt.id
                    ? 'border-primary ring-2 ring-primary/20 bg-surface'
                    : 'border-outline-variant bg-surface/50 hover:border-primary/50'
                ]"
                :data-testid="`reaction-opt-${opt.id}`"
                @click="onReactionSelect(opt.id)"
              >
                <div class="flex items-center justify-between">
                  <span class="font-title-sm text-xs font-semibold text-on-surface">{{ opt.title }}</span>
                  <div
                    class="w-3 h-3 rounded-full border"
                    :class="drawdownReaction === opt.id ? 'bg-primary border-primary' : 'border-outline'"
                  ></div>
                </div>
                <span class="text-[11px] text-on-surface-variant leading-tight">{{ opt.description }}</span>
              </button>
            </div>
          </div>

          <!-- Derived Tier Badge -->
          <div class="flex items-center justify-between p-sm bg-surface rounded-md border border-outline-variant/30">
            <div class="flex items-center gap-sm">
              <span class="font-label-caps text-xs text-on-surface-variant uppercase">Calibrated Risk Tier:</span>
              <span class="font-title-sm text-sm capitalize font-bold text-on-surface" data-testid="derived-risk-tier">
                {{ riskTolerance }}
              </span>
            </div>
            <select
              v-model="riskTolerance"
              class="px-sm py-1 text-xs rounded bg-surface-container border border-outline-variant font-medium text-on-surface"
              data-testid="select-risk-tier"
            >
              <option value="conservative">Conservative</option>
              <option value="moderate">Moderate</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </div>

          <!-- Allocation Visual & Sliders -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-md items-center pt-sm border-t border-outline-variant/30">
            <!-- Donut Chart & Projected Return (5 cols) -->
            <div class="lg:col-span-5 flex flex-col items-center justify-center p-md bg-surface rounded-lg border border-outline-variant/30">
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
                    stroke-width="12"
                    :stroke-dasharray="`${arc.len} 251.2`"
                    :stroke-dashoffset="arc.offset"
                    class="transition-all duration-500 ease-out"
                  ></circle>
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span class="font-title-sm text-sm text-on-surface font-mono font-bold" data-testid="total-percent-display">{{ totalTargetPercent }}%</span>
                  <span class="text-[9px] uppercase font-label-caps text-on-surface-variant">Target</span>
                </div>
              </div>
              <div class="mt-sm flex items-center gap-sm text-xs">
                <span class="text-on-surface-variant">Projected Return:</span>
                <span class="font-mono font-bold text-on-surface" data-testid="projected-return">{{ projectedReturn }}</span>
              </div>
            </div>

            <!-- Sliders and Min/Max Bounds (7 cols) -->
            <div class="lg:col-span-7 flex flex-col gap-sm">
              <div
                v-for="(band, idx) in bands"
                :key="band.asset_class"
                class="p-sm rounded-md bg-surface border border-outline-variant/30 flex flex-col gap-1"
                data-testid="band-row"
              >
                <div class="flex justify-between items-center text-xs">
                  <span class="font-medium text-on-surface">{{ band.asset_class }}</span>
                  <div class="flex items-center gap-1 font-mono">
                    <input
                      v-model.number="band.target_percent"
                      type="number"
                      min="0"
                      max="100"
                      class="w-12 text-center bg-surface-container py-0.5 rounded border border-outline-variant text-xs"
                      :data-testid="`input-target-${idx}`"
                    />
                    <span>%</span>
                  </div>
                </div>

                <input
                  v-model.number="band.target_percent"
                  type="range"
                  min="0"
                  max="100"
                  class="w-full h-1.5 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-primary"
                  :data-testid="`slider-target-${idx}`"
                />

                <div class="flex items-center justify-between text-[11px] text-on-surface-variant font-mono pt-1">
                  <span>Drift Bounds:</span>
                  <div class="flex items-center gap-1">
                    <span>Min:</span>
                    <input
                      v-model.number="band.min_percent"
                      type="number"
                      min="0"
                      max="100"
                      class="w-10 text-center bg-surface-container py-0.5 rounded border border-outline-variant text-[11px]"
                      :data-testid="`input-min-${idx}`"
                    />
                    <span>% – Max:</span>
                    <input
                      v-model.number="band.max_percent"
                      type="number"
                      min="0"
                      max="100"
                      class="w-10 text-center bg-surface-container py-0.5 rounded border border-outline-variant text-[11px]"
                      :data-testid="`input-max-${idx}`"
                    />
                    <span>%</span>
                  </div>
                </div>
              </div>

              <div
                v-if="totalTargetPercent !== 100"
                class="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs flex items-center gap-1.5"
                data-testid="allocation-warning"
              >
                <span class="material-symbols-outlined text-[16px]">warning</span>
                <span>Total allocation must equal 100% (currently {{ totalTargetPercent }}%).</span>
              </div>
            </div>
          </div>

          <!-- Risk Notes -->
          <div class="flex flex-col gap-xs pt-sm border-t border-outline-variant/30">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Risk Tolerance &amp; Market Volatility Comfort (Notes)</label>
            <textarea
              v-model="riskToleranceNotes"
              rows="2"
              placeholder="Describe your personal comfort with market volatility and drawdown scenarios..."
              class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm resize-none"
              data-testid="textarea-risk-notes"
            ></textarea>
          </div>
        </div>
      </div>

      <!-- TAB 4: Liabilities & Debt -->
      <div v-show="activeTab === 'liabilities'" class="flex flex-col gap-lg" data-testid="section-liabilities">
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant/30 pb-sm">
            <div class="flex items-center gap-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">credit_card</span>
              <h2 class="font-title-sm text-on-surface font-semibold">Current Liabilities &amp; Outstanding Debt</h2>
            </div>
            <button
              v-if="!hasNoDebt"
              type="button"
              @click="addLiability"
              class="px-sm py-xs text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 rounded-md flex items-center gap-xs transition-colors"
              data-testid="btn-add-liability"
            >
              <span class="material-symbols-outlined text-[16px]">add</span>
              Add Liability
            </button>
          </div>

          <!-- Zero Debt Toggle -->
          <div class="flex items-center justify-between p-sm bg-surface rounded-md border border-outline-variant/30">
            <div>
              <span class="font-title-sm text-xs font-semibold text-on-surface block">Zero Outstanding Debt</span>
              <span class="text-xs text-on-surface-variant">Check if you carry no loans, mortgages, or credit card balances.</span>
            </div>
            <input
              v-model="hasNoDebt"
              type="checkbox"
              class="w-5 h-5 accent-primary cursor-pointer"
              data-testid="toggle-no-debt"
            />
          </div>

          <!-- Debt Items List -->
          <div v-if="!hasNoDebt" class="flex flex-col gap-md">
            <div
              v-for="(item, idx) in liabilities"
              :key="item.liability_id || idx"
              class="bg-surface p-md rounded-lg border border-outline-variant/40 flex flex-col gap-sm"
              data-testid="liability-item-row"
            >
              <div class="flex items-center justify-between border-b border-outline-variant/20 pb-xs">
                <span class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Liability #{{ idx + 1 }}</span>
                <button
                  type="button"
                  @click="removeLiability(idx)"
                  class="text-on-surface-variant hover:text-red-500 text-xs flex items-center gap-1"
                  data-testid="btn-remove-liability"
                >
                  <span class="material-symbols-outlined text-[16px]">delete</span>
                  <span>Remove</span>
                </button>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Description</label>
                  <input
                    v-model="item.description"
                    type="text"
                    placeholder="e.g. Premium Rewards Card, Mortgage"
                    class="px-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface text-sm focus:outline-none focus:border-primary"
                    data-testid="input-liability-desc"
                  />
                </div>

                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Category</label>
                  <select
                    v-model="item.type"
                    class="px-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface text-sm focus:outline-none focus:border-primary"
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
                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Balance ($ USD)</label>
                  <input
                    v-model.number="item.balance_usd"
                    type="number"
                    min="0"
                    placeholder="0"
                    class="px-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                    data-testid="input-liability-balance"
                  />
                </div>

                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Interest APR (%)</label>
                  <input
                    v-model.number="item.interest_rate_percent"
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    placeholder="0"
                    class="px-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                    data-testid="input-liability-apr"
                  />
                </div>

                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Min Monthly Payment ($)</label>
                  <input
                    v-model.number="item.minimum_payment_usd"
                    type="number"
                    min="0"
                    placeholder="0"
                    class="px-md py-sm rounded-md bg-surface-container border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                    data-testid="input-liability-min-payment"
                  />
                </div>
              </div>

              <div
                v-if="item.interest_rate_percent >= 15"
                class="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs flex items-center gap-1.5"
              >
                <span class="material-symbols-outlined text-[16px]">warning</span>
                <span>High-interest debt ({{ item.interest_rate_percent }}% APR) is flagged for debt-paydown prioritization before aggressive equity allocation.</span>
              </div>
            </div>
          </div>

          <!-- Total Liabilities Display -->
          <div class="flex justify-between items-center p-sm bg-surface rounded-md border border-outline-variant/30 font-mono text-xs">
            <span class="text-on-surface-variant">Total Reported Liabilities:</span>
            <span class="font-bold text-on-surface" data-testid="total-liabilities-display">
              ${{ totalLiabilities.toLocaleString() }}
            </span>
          </div>
        </div>
      </div>

      <!-- TAB 5: Policy Guardrails & Constraints -->
      <div v-show="activeTab === 'policy'" class="flex flex-col gap-lg" data-testid="section-policy">
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center gap-sm border-b border-outline-variant/30 pb-sm">
            <span class="material-symbols-outlined text-primary text-[20px]">gavel</span>
            <h2 class="font-title-sm text-on-surface font-semibold">Policy Guardrails &amp; HITL Sign-offs</h2>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Emergency Reserve (Months)</label>
              <input
                v-model.number="reserveMonths"
                type="number"
                min="1"
                max="36"
                placeholder="6"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                data-testid="input-reserve-months"
              />
              <span class="text-[11px] text-on-surface-variant">Recommended: 3–6 months of living expenses.</span>
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Max Single-Stock Concentration (%)</label>
              <input
                v-model.number="concentrationLimit"
                type="number"
                min="1"
                max="50"
                placeholder="15"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                data-testid="input-concentration-limit"
              />
              <span class="text-[11px] text-on-surface-variant">Default limit: 15% per holding.</span>
            </div>

            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Account Type</label>
              <select
                v-model="accountType"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface text-sm focus:outline-none focus:border-primary"
                data-testid="select-account-type"
              >
                <option value="taxable">Individual Taxable Brokerage</option>
                <option value="retirement">Retirement (IRA / Roth / 401k)</option>
              </select>
            </div>

            <div class="flex flex-col justify-center gap-xs">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Tax-Loss Harvesting</label>
              <label class="flex items-center gap-2 cursor-pointer mt-1">
                <input
                  v-model="taxLossHarvesting"
                  type="checkbox"
                  class="w-5 h-5 accent-primary cursor-pointer"
                  data-testid="toggle-tax-loss"
                />
                <span class="text-sm text-on-surface">Enable automated TLH scans</span>
              </label>
            </div>

            <div class="flex flex-col gap-xs md:col-span-2 pt-sm border-t border-outline-variant/30">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Excluded Tickers (Comma-separated)</label>
              <input
                v-model="excludedTickersStr"
                type="text"
                placeholder="e.g. TSLA, XOM, BABA"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                data-testid="input-excluded-tickers"
              />
            </div>

            <div class="flex flex-col gap-xs md:col-span-2">
              <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Excluded Sectors (Comma-separated)</label>
              <input
                v-model="excludedSectorsStr"
                type="text"
                placeholder="e.g. tobacco, defense, fossil_fuels"
                class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                data-testid="input-excluded-sectors"
              />
            </div>

            <!-- HITL Sign-off Thresholds -->
            <div class="flex flex-col gap-xs md:col-span-2 pt-sm border-t border-outline-variant/30">
              <label class="font-title-sm text-sm text-on-surface font-semibold">Autonomous Trade Governance (HITL Thresholds)</label>
              <span class="text-xs text-on-surface-variant mb-1">Trades exceeding either threshold require explicit human approval.</span>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-md mt-1">
                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Require Approval Above ($ USD)</label>
                  <input
                    v-model.number="approvalAboveUsd"
                    type="number"
                    min="0"
                    placeholder="1000"
                    class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                    data-testid="input-approval-usd"
                  />
                </div>
                <div class="flex flex-col gap-xs">
                  <label class="font-label-caps text-xs text-on-surface-variant uppercase">Require Approval Above (% of Portfolio)</label>
                  <input
                    v-model.number="approvalAbovePct"
                    type="number"
                    min="0.1"
                    max="100"
                    placeholder="5"
                    class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono text-sm focus:outline-none focus:border-primary"
                    data-testid="input-approval-pct"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 6: Income & Tax Documents -->
      <div v-show="activeTab === 'income'" class="flex flex-col gap-lg" data-testid="section-income">
        <!-- W-2 Upload & Document AI Processing Card -->
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant/30 pb-sm">
            <div class="flex items-center gap-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">document_scanner</span>
              <h2 class="font-title-sm text-on-surface font-semibold">IRS Form W-2 Statement Ingestion</h2>
            </div>
            <span class="text-xs text-on-surface-variant font-mono bg-surface-container-high px-2 py-0.5 rounded">
              Powered by Google Cloud Document AI
            </span>
          </div>

          <p class="text-xs text-on-surface-variant">
            Upload your official IRS Form W-2 (Wage and Tax Statement) in PDF, PNG, or JPG formats (max 10MB).
            Document AI will automatically extract gross compensation, federal/state withholdings, and Box 12 retirement deferrals.
          </p>

          <!-- Upload Dropzone -->
          <div
            class="border-2 border-dashed rounded-lg p-lg flex flex-col items-center justify-center text-center cursor-pointer transition-colors"
            :class="[
              isDraggingW2
                ? 'border-primary bg-primary/5'
                : 'border-outline-variant hover:border-primary/60 hover:bg-surface-container-high/40'
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

            <div v-if="isUploadingW2" class="flex flex-col items-center gap-sm py-md">
              <span class="material-symbols-outlined text-primary text-[32px] animate-spin">progress_activity</span>
              <span class="text-sm font-medium text-on-surface">Parsing W-2 with Google Cloud Document AI...</span>
              <span class="text-xs text-on-surface-variant">Extracting Boxes 1–20 and verifying employer records</span>
            </div>

            <div v-else class="flex flex-col items-center gap-xs py-sm">
              <span class="material-symbols-outlined text-primary text-[36px]">upload_file</span>
              <span class="text-sm font-medium text-on-surface">
                Drag &amp; drop your W-2 here, or <span class="text-primary underline">browse files</span>
              </span>
              <span class="text-xs text-on-surface-variant">
                Supported formats: PDF, PNG, JPG (up to 10MB)
              </span>
            </div>
          </div>

          <!-- Status Banners for W-2 -->
          <div
            v-if="w2UploadSuccess"
            class="p-sm rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 flex items-center justify-between text-xs"
            data-testid="w2-upload-success"
          >
            <div class="flex items-center gap-xs">
              <span class="material-symbols-outlined text-[16px]">check_circle</span>
              <span>{{ w2UploadSuccess }}</span>
            </div>
            <button type="button" class="underline hover:opacity-80" @click="w2UploadSuccess = null">Dismiss</button>
          </div>

          <div
            v-if="w2UploadError"
            class="p-sm rounded-md bg-red-500/10 border border-red-500/30 text-red-600 flex items-center justify-between text-xs"
            data-testid="w2-upload-error"
          >
            <div class="flex items-center gap-xs">
              <span class="material-symbols-outlined text-[16px]">error</span>
              <span>{{ w2UploadError }}</span>
            </div>
            <button type="button" class="underline hover:opacity-80" @click="w2UploadError = null">Dismiss</button>
          </div>
        </div>

        <!-- Ingested W-2 Statements List & Breakdowns -->
        <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
          <div class="flex items-center justify-between border-b border-outline-variant/30 pb-sm">
            <div class="flex items-center gap-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">receipt_long</span>
              <h2 class="font-title-sm text-on-surface font-semibold">Verified Tax Statements History</h2>
            </div>
            <button
              type="button"
              class="text-xs text-primary hover:underline flex items-center gap-xs"
              data-testid="btn-refresh-w2"
              @click="loadW2Documents"
            >
              <span class="material-symbols-outlined text-[14px]">refresh</span>
              Refresh
            </button>
          </div>

          <div v-if="loadingW2" class="p-lg text-center text-sm text-on-surface-variant">
            Loading verified statements...
          </div>

          <div v-else-if="w2Documents.length === 0" class="p-lg text-center text-sm text-on-surface-variant flex flex-col items-center gap-xs">
            <span class="material-symbols-outlined text-outline text-[32px]">folder_open</span>
            <span>No W-2 statements uploaded yet. Upload a tax statement above to verify your income.</span>
          </div>

          <div v-else class="flex flex-col gap-md">
            <div
              v-for="w2 in w2Documents"
              :key="w2.id"
              class="border border-outline-variant/60 rounded-lg p-md bg-surface flex flex-col gap-sm shadow-xs"
              data-testid="w2-card"
            >
              <!-- Card Header -->
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-sm border-b border-outline-variant/30 pb-xs">
                <div class="flex items-center gap-sm">
                  <span class="px-2 py-0.5 rounded text-xs font-mono font-bold bg-primary-container text-on-primary">
                    Tax Year {{ w2.tax_year }}
                  </span>
                  <span class="font-semibold text-sm text-on-surface">{{ w2.employer?.name || 'Employer' }}</span>
                  <span v-if="w2.employer?.ein" class="text-xs text-on-surface-variant font-mono">
                    EIN: {{ w2.employer.ein }}
                  </span>
                </div>

                <div class="flex items-center gap-xs">
                  <button
                    type="button"
                    class="px-sm py-1 rounded bg-primary/10 hover:bg-primary/20 text-primary text-xs font-medium transition flex items-center gap-1"
                    data-testid="btn-apply-w2"
                    :disabled="applyingW2Id === w2.id"
                    @click="handleApplyW2(w2)"
                  >
                    <span class="material-symbols-outlined text-[14px]">sync_alt</span>
                    {{ applyingW2Id === w2.id ? 'Applying...' : 'Apply to Profile Income' }}
                  </button>

                  <button
                    type="button"
                    class="p-1 rounded text-on-surface-variant hover:text-red-600 hover:bg-surface-container transition"
                    title="Delete W-2"
                    data-testid="btn-delete-w2"
                    @click="handleDeleteW2(w2.id)"
                  >
                    <span class="material-symbols-outlined text-[16px]">delete</span>
                  </button>
                </div>
              </div>

              <!-- Main Financial Metrics Grid -->
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-sm pt-xs">
                <div class="flex flex-col bg-surface-container/60 p-xs rounded">
                  <span class="text-[10px] uppercase font-label-caps text-on-surface-variant">Box 1: Wages &amp; Tips</span>
                  <span class="text-sm font-bold font-mono text-on-surface" data-testid="w2-box1-wages">
                    ${{ (w2.wages_and_compensation?.box1_wages_tips_other_comp_usd ?? 0).toLocaleString() }}
                  </span>
                </div>

                <div class="flex flex-col bg-surface-container/60 p-xs rounded">
                  <span class="text-[10px] uppercase font-label-caps text-on-surface-variant">Box 2: Federal Tax</span>
                  <span class="text-sm font-mono text-on-surface">
                    ${{ (w2.wages_and_compensation?.box2_federal_income_tax_withheld_usd ?? 0).toLocaleString() }}
                  </span>
                </div>

                <div class="flex flex-col bg-surface-container/60 p-xs rounded">
                  <span class="text-[10px] uppercase font-label-caps text-on-surface-variant">Box 3: SS Wages</span>
                  <span class="text-sm font-mono text-on-surface">
                    ${{ (w2.wages_and_compensation?.box3_social_security_wages_usd ?? 0).toLocaleString() }}
                  </span>
                </div>

                <div class="flex flex-col bg-surface-container/60 p-xs rounded">
                  <span class="text-[10px] uppercase font-label-caps text-on-surface-variant">Box 5: Medicare Wages</span>
                  <span class="text-sm font-mono text-on-surface">
                    ${{ (w2.wages_and_compensation?.box5_medicare_wages_and_tips_usd ?? 0).toLocaleString() }}
                  </span>
                </div>
              </div>

              <!-- Box 12 Items (e.g. 401(k), HSA) if present -->
              <div v-if="w2.box12_items && w2.box12_items.length > 0" class="flex flex-wrap items-center gap-xs pt-xs">
                <span class="text-[10px] uppercase font-label-caps text-on-surface-variant mr-1">Box 12 Benefits:</span>
                <span
                  v-for="(item, idx) in w2.box12_items"
                  :key="idx"
                  class="px-2 py-0.5 rounded-full text-xs font-mono bg-surface-container-high border border-outline-variant/40"
                >
                  Code {{ item.code }}: ${{ item.amount_usd.toLocaleString() }}
                  <span v-if="item.description" class="text-[10px] text-on-surface-variant font-sans">({{ item.description }})</span>
                </span>
              </div>

              <!-- State Taxes if present -->
              <div v-if="w2.state_taxes && w2.state_taxes.length > 0" class="flex flex-wrap items-center gap-xs pt-xs">
                <span class="text-[10px] uppercase font-label-caps text-on-surface-variant mr-1">State Taxes:</span>
                <span
                  v-for="(st, sIdx) in w2.state_taxes"
                  :key="sIdx"
                  class="px-2 py-0.5 rounded text-xs font-mono bg-surface-container-high"
                >
                  {{ st.state }}: Wages ${{ st.state_wages_usd.toLocaleString() }}, Tax ${{ st.state_income_tax_usd.toLocaleString() }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Footer -->
      <div class="flex items-center justify-between pt-sm border-t border-outline-variant/40">
        <button
          type="button"
          @click="resetAllForms"
          class="px-md py-sm text-sm font-medium text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-md transition"
          :disabled="isSaving"
          data-testid="btn-reset-profile"
        >
          Reset to Saved
        </button>

        <button
          type="submit"
          class="px-lg py-sm text-sm font-medium bg-primary text-on-primary hover:bg-primary/90 rounded-md transition flex items-center gap-xs shadow-sm disabled:opacity-50"
          :disabled="isSaving"
          data-testid="btn-save-profile"
          @click.prevent="handleSave"
        >
          <span v-if="isSaving" class="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
          <span v-else class="material-symbols-outlined text-[16px]">save</span>
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

// 1. Personal & Family State
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

// 2. Goals & Timeline State
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

// 3. Risk Calibration & Allocation State
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
    description: 'Liquidate equities to cash / treasuries to prevent further portfolio drawdown.'
  }
];

// 4. Liabilities & Debt State
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

// 5. Policy Guardrails & HITL Sign-offs State
const reserveMonths = ref(6);
const concentrationLimit = ref(15);
const accountType = ref<'taxable' | 'retirement'>('taxable');
const taxLossHarvesting = ref(true);
const excludedTickersStr = ref('');
const excludedSectorsStr = ref('');
const approvalAboveUsd = ref(1000);
const approvalAbovePct = ref(5);

// Snapshots for reset
const initialProfileSnapshot = ref<UserProfile | null>(null);
const initialOnboardingSnapshot = ref<OnboardingProfile | null>(null);

// Computed Calculations
const totalLiabilities = computed(() => {
  if (hasNoDebt.value) return 0;
  return liabilities.value.reduce((acc, l) => acc + (Number(l.balance_usd) || 0), 0);
});

const totalTargetPercent = computed(() => {
  return bands.value.reduce((sum, b) => sum + (Number(b.target_percent) || 0), 0);
});

const CIRCUMFERENCE = 251.2;
const arcColors = ['#131b2e', '#b9c7e0', '#565e74', '#7890cd', '#e2e8f0'];

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

// Methods
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
  } catch (err: any) {
    saveError.value = 'Failed to load initial settings.';
  }
}

// 6. Income & Tax (W-2) State & Handlers
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
    w2UploadSuccess.value = `Successfully parsed Form W-2 (${doc.tax_year}) for ${doc.employer?.name || 'employer'} with Document AI! Box 1 Wages: $${doc.wages_and_compensation.box1_wages_tips_other_comp_usd.toLocaleString()}`;
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
      w2UploadSuccess.value = `Successfully synchronized Box 1 wages ($${doc.wages_and_compensation.box1_wages_tips_other_comp_usd.toLocaleString()}) to Profile Annual Income!`;
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
    // 1. Save User Profile
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

    // 2. Save Active IPS & Liabilities
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
