<template>
  <div class="flex flex-col gap-lg w-full max-w-4xl mx-auto pb-xl" data-testid="profile-view">
    <!-- Header -->
    <div class="flex flex-col gap-xs">
      <div class="flex items-center gap-xs text-primary font-label-caps text-label-caps uppercase">
        <span class="material-symbols-outlined text-[18px]">badge</span>
        Personal Planning Profile
      </div>
      <h1 class="font-headline-lg-mobile text-headline-lg-mobile text-on-background">User Profile & Planning Context</h1>
      <p class="font-body-base text-body-base text-on-surface-variant max-w-2xl">
        Manage personal demographics, family members, and career milestones used by the copilot to calibrate risk parameters, savings targets, and financial projections.
      </p>
    </div>

    <!-- Alert / Status Banners -->
    <div
      v-if="saveSuccess"
      class="p-md rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 flex items-center justify-between"
      data-testid="profile-save-success"
    >
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-emerald-600 text-[20px]">check_circle</span>
        <span class="font-medium text-sm">Profile updated and saved to database.</span>
      </div>
      <button class="text-xs text-emerald-600 hover:underline" @click="saveSuccess = false">Dismiss</button>
    </div>

    <div
      v-if="saveError"
      class="p-md rounded-md bg-red-500/10 border border-red-500/30 text-red-600 flex items-center justify-between"
      data-testid="profile-save-error"
    >
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-red-600 text-[20px]">error</span>
        <span class="font-medium text-sm">{{ saveError }}</span>
      </div>
      <button class="text-xs text-red-600 hover:underline" @click="saveError = null">Dismiss</button>
    </div>

    <form @submit.prevent="handleSave" class="flex flex-col gap-lg">
      <!-- Section 1: Personal Details -->
      <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
        <div class="flex items-center gap-sm border-b border-outline-variant/30 pb-sm">
          <span class="material-symbols-outlined text-primary text-[20px]">person</span>
          <h2 class="font-title-sm text-on-surface font-semibold">Personal Information</h2>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Full Name</label>
            <input
              v-model="form.full_name"
              type="text"
              placeholder="e.g. Alex Mercer"
              class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
              data-testid="input-full-name"
            />
          </div>

          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Email Address</label>
            <input
              v-model="form.email"
              type="email"
              placeholder="e.g. alex.mercer@example.com"
              class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
              data-testid="input-email"
            />
          </div>

          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Date of Birth</label>
            <input
              v-model="form.date_of_birth"
              type="date"
              @change="calculateAgeFromDOB"
              class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm"
              data-testid="input-dob"
            />
          </div>

          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Age</label>
            <input
              v-model.number="form.age"
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
              v-model="form.marital_status"
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

      <!-- Section 2: Family & Dependents -->
      <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
        <div class="flex items-center justify-between border-b border-outline-variant/30 pb-sm">
          <div class="flex items-center gap-sm">
            <span class="material-symbols-outlined text-primary text-[20px]">group</span>
            <h2 class="font-title-sm text-on-surface font-semibold">Family & Dependents</h2>
          </div>
          <button
            type="button"
            @click="addFamilyMember"
            class="px-sm py-xs text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 rounded-md flex items-center gap-xs"
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
              v-model.number="form.dependents_count"
              type="number"
              min="0"
              class="w-24 px-md py-xs rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
              data-testid="input-dependents-count"
            />
          </div>

          <!-- Family Members Table / List -->
          <div v-if="form.family_members && form.family_members.length > 0" class="flex flex-col gap-xs mt-sm">
            <div
              v-for="(member, idx) in form.family_members"
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

      <!-- Section 3: Career & Financial Targets -->
      <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
        <div class="flex items-center gap-sm border-b border-outline-variant/30 pb-sm">
          <span class="material-symbols-outlined text-primary text-[20px]">work</span>
          <h2 class="font-title-sm text-on-surface font-semibold">Career & Financial Parameters</h2>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Employment Status</label>
            <select
              v-model="form.employment_status"
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
              v-model="form.occupation"
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
                v-model.number="form.annual_income_usd"
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
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Target Retirement Age</label>
            <input
              v-model.number="form.target_retirement_age"
              type="number"
              min="30"
              max="100"
              placeholder="62"
              class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface font-mono focus:outline-none focus:border-primary text-sm"
              data-testid="input-target-retirement-age"
            />
          </div>

          <div class="flex flex-col gap-xs md:col-span-2">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Monthly Rent / Mortgage (USD)</label>
            <div class="relative">
              <span class="absolute left-3 top-2.5 text-on-surface-variant text-sm font-mono">$</span>
              <input
                v-model.number="form.monthly_housing_payment_usd"
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

      <!-- Section 4: Context & Goals Notes -->
      <div class="bg-surface-container rounded-lg p-lg border border-outline-variant/50 flex flex-col gap-md">
        <div class="flex items-center gap-sm border-b border-outline-variant/30 pb-sm">
          <span class="material-symbols-outlined text-primary text-[20px]">notes</span>
          <h2 class="font-title-sm text-on-surface font-semibold">Goals & Context Notes</h2>
        </div>

        <div class="flex flex-col gap-md">
          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Risk Tolerance & Market Volatility Comfort</label>
            <textarea
              v-model="form.risk_tolerance_notes"
              rows="2"
              placeholder="Describe your comfort level with drawdowns and volatility..."
              class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm resize-none"
              data-testid="textarea-risk-notes"
            ></textarea>
          </div>

          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase font-medium">Long-Term Milestones & Family Objectives</label>
            <textarea
              v-model="form.financial_goals_notes"
              rows="2"
              placeholder="Key upcoming milestones (e.g. college savings, early retirement, property purchase)..."
              class="px-md py-sm rounded-md bg-surface border border-outline-variant text-on-surface focus:outline-none focus:border-primary text-sm resize-none"
              data-testid="textarea-goals-notes"
            ></textarea>
          </div>
        </div>
      </div>

      <!-- Form Actions -->
      <div class="flex items-center justify-between pt-sm">
        <button
          type="button"
          @click="resetForm"
          class="px-md py-sm text-sm font-medium text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-md transition"
          :disabled="isSaving"
          data-testid="btn-reset-profile"
        >
          Reset
        </button>

        <button
          type="submit"
          class="px-lg py-sm text-sm font-medium bg-primary text-on-primary hover:bg-primary/90 rounded-md transition flex items-center gap-xs shadow-sm"
          :disabled="isSaving"
          data-testid="btn-save-profile"
        >
          <span v-if="isSaving" class="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
          <span v-else class="material-symbols-outlined text-[16px]">save</span>
          {{ isSaving ? 'Saving Profile...' : 'Save Profile' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import type { UserProfile, FamilyMember } from '../types';
import { apiService } from '../services/api';

const isSaving = ref(false);
const saveSuccess = ref(false);
const saveError = ref<string | null>(null);
const initialProfile = ref<UserProfile | null>(null);

const form = reactive<UserProfile>({
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

function calculateAgeFromDOB() {
  if (!form.date_of_birth) return;
  const dob = new Date(form.date_of_birth);
  if (isNaN(dob.getTime())) return;
  const today = new Date();
  let calculatedAge = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    calculatedAge--;
  }
  if (calculatedAge >= 0) {
    form.age = calculatedAge;
  }
}

function addFamilyMember() {
  form.family_members = form.family_members || [];
  form.family_members.push({
    name: '',
    relationship: 'child',
    age: 0
  });
}

function removeFamilyMember(index: number) {
  if (form.family_members) {
    form.family_members.splice(index, 1);
  }
}

function populateForm(profile: UserProfile) {
  form.user_id = profile.user_id || 'demo_user';
  form.full_name = profile.full_name || '';
  form.email = profile.email || '';
  form.date_of_birth = profile.date_of_birth || '';
  form.age = profile.age;
  form.marital_status = profile.marital_status || 'single';
  form.dependents_count = profile.dependents_count ?? 0;
  form.family_members = (profile.family_members || []).map((m: FamilyMember) => ({ ...m }));
  form.employment_status = profile.employment_status || 'employed';
  form.occupation = profile.occupation || '';
  form.annual_income_usd = profile.annual_income_usd;
  form.target_retirement_age = profile.target_retirement_age;
  form.monthly_housing_payment_usd = profile.monthly_housing_payment_usd;
  form.risk_tolerance_notes = profile.risk_tolerance_notes || '';
  form.financial_goals_notes = profile.financial_goals_notes || '';
  form.updated_at = profile.updated_at || '';
}

function resetForm() {
  if (initialProfile.value) {
    populateForm(initialProfile.value);
  }
}

async function loadProfile() {
  try {
    const data = await apiService.getUserProfile('demo_user');
    initialProfile.value = JSON.parse(JSON.stringify(data));
    populateForm(data);
  } catch (err) {
    saveError.value = 'Failed to load user profile.';
  }
}

async function handleSave() {
  isSaving.value = true;
  saveSuccess.value = false;
  saveError.value = null;

  try {
    const payload: UserProfile = {
      ...form,
      user_id: form.user_id || 'demo_user'
    };
    const res = await apiService.updateUserProfile(payload);
    if (res && res.profile) {
      initialProfile.value = JSON.parse(JSON.stringify(res.profile));
      populateForm(res.profile);
    }
    saveSuccess.value = true;
  } catch (err: any) {
    saveError.value = err?.message || 'Failed to save profile. Please check your inputs.';
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  loadProfile();
});
</script>
