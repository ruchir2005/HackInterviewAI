"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Briefcase,
  Code2,
  GraduationCap,
  School,
  User,
  Check,
  ChevronRight,
  ChevronLeft,
  Search,
  ArrowRight,
} from "lucide-react";

// ─── Data ──────────────────────────────────────────────
const PRIMARY_TYPES = [
  {
    id: "job-role",
    title: "Job Role Based",
    description:
      "Practice interview questions tailored to specific job roles like Software Engineer, Product Manager, or Data Analyst.",
    icon: Briefcase,
    gradient: "from-orange-500/20 to-amber-500/20",
    accentColor: "text-orange-500",
    borderColor: "border-orange-500/40",
    glowColor: "shadow-orange-500/20",
  },
  {
    id: "skill",
    title: "Skill Based",
    description:
      "Focus on specific skills such as React, Python, SQL, or Machine Learning with targeted practice questions.",
    icon: Code2,
    gradient: "from-blue-500/20 to-cyan-500/20",
    accentColor: "text-blue-500",
    borderColor: "border-blue-500/40",
    glowColor: "shadow-blue-500/20",
  },
  {
    id: "institution",
    title: "Institution Based",
    description:
      "Interview preparation curated for specific colleges and institutions with domain-specific focus areas.",
    icon: GraduationCap,
    gradient: "from-purple-500/20 to-pink-500/20",
    accentColor: "text-purple-500",
    borderColor: "border-purple-500/40",
    glowColor: "shadow-purple-500/20",
  },
] as const;

const INSTITUTION_SUB_TYPES = [
  {
    id: "college",
    title: "College Based",
    description:
      "Select your college and domain for a tailored, academic-style interview experience.",
    icon: School,
    gradient: "from-emerald-500/20 to-teal-500/20",
    accentColor: "text-emerald-500",
    borderColor: "border-emerald-500/40",
    glowColor: "shadow-emerald-500/20",
  },
  {
    id: "individual",
    title: "Individual Interview Type",
    description:
      "Choose specific interview categories like HR, DSA, System Design, and more.",
    icon: User,
    gradient: "from-violet-500/20 to-indigo-500/20",
    accentColor: "text-violet-500",
    borderColor: "border-violet-500/40",
    glowColor: "shadow-violet-500/20",
  },
] as const;

const COLLEGES = [
  "Indian Institute of Technology, Bombay",
  "Indian Institute of Technology, Delhi",
  "Indian Institute of Technology, Madras",
  "Indian Institute of Technology, Kanpur",
  "Indian Institute of Technology, Kharagpur",
  "National Institute of Technology, Trichy",
  "National Institute of Technology, Warangal",
  "National Institute of Technology, Surathkal",
  "Birla Institute of Technology and Science, Pilani",
  "Vellore Institute of Technology",
  "SRM Institute of Science and Technology",
  "Manipal Institute of Technology",
  "Delhi Technological University",
  "Netaji Subhas University of Technology",
  "Amity University",
  "Lovely Professional University",
  "Shiv Nadar University",
  "IIIT Hyderabad",
  "IIIT Delhi",
  "PES University",
  "Woxsen University",
];

const COLLEGE_DOMAINS = [
  "School of Technology",
  "School of Engineering",
  "School of Computer Science",
  "School of Business",
  "School of Management",
  "School of Design",
  "School of Sciences",
  "School of Law",
  "School of Arts & Humanities",
  "School of Medicine",
];

const INTERVIEW_CHIPS = [
  { id: "hr", label: "HR Interview", emoji: "🤝" },
  { id: "dsa", label: "DSA Interview", emoji: "🧮" },
  { id: "system-design", label: "System Design", emoji: "🏗️" },
  { id: "core-subject", label: "Core Subject", emoji: "📚" },
  { id: "behavioral", label: "Behavioral", emoji: "🎯" },
  { id: "technical", label: "Technical", emoji: "💻" },
];

// ─── Animation variants ────────────────────────────────
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.05 },
  },
  exit: { opacity: 0, transition: { duration: 0.2 } },
};

const cardVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 300, damping: 25 },
  },
  exit: { opacity: 0, y: -20, scale: 0.95, transition: { duration: 0.2 } },
};

const panelVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 250, damping: 22, delay: 0.1 },
  },
  exit: { opacity: 0, y: 20, scale: 0.98, transition: { duration: 0.2 } },
};

const chipVariants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: (i: number) => ({
    opacity: 1,
    scale: 1,
    transition: { delay: i * 0.06, type: "spring" as const, stiffness: 400, damping: 20 },
  }),
};

// ─── Component ─────────────────────────────────────────
export default function InterviewSelectionPage() {
  const router = useRouter();

  // Tier 1
  const [selectedPrimary, setSelectedPrimary] = useState<string | null>(null);
  // Tier 2 (institution sub)
  const [selectedInstitution, setSelectedInstitution] = useState<string | null>(null);
  // Tier 3a – college form
  const [collegeSearch, setCollegeSearch] = useState("");
  const [selectedCollege, setSelectedCollege] = useState<string | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [isCollegeDropdownOpen, setIsCollegeDropdownOpen] = useState(false);
  // Tier 3b – individual chips
  const [selectedChips, setSelectedChips] = useState<Set<string>>(new Set());

  // Filtered college list
  const filteredColleges = useMemo(
    () =>
      COLLEGES.filter((c) =>
        c.toLowerCase().includes(collegeSearch.toLowerCase())
      ),
    [collegeSearch]
  );

  // ── Helpers ──
  const toggleChip = (id: string) => {
    setSelectedChips((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBack = () => {
    if (selectedInstitution) {
      setSelectedInstitution(null);
      setCollegeSearch("");
      setSelectedCollege(null);
      setSelectedDomain(null);
      setIsCollegeDropdownOpen(false);
      setSelectedChips(new Set());
    } else if (selectedPrimary === "institution") {
      setSelectedPrimary(null);
    } else {
      setSelectedPrimary(null);
    }
  };

  const canStart = !!selectedPrimary;

  const handleStart = () => {
    if (!canStart) return;

    // Institution access is resolved from the signed-in user's verified
    // server-side memberships. UI selection/query parameters grant nothing.
    if (selectedPrimary === "institution") {
      router.push("/institution");
      return;
    }

    const params = new URLSearchParams();
    params.set("type", selectedPrimary!);

    router.push(`/resume?${params.toString()}`);
  };

  // Current breadcrumb trail
  const breadcrumbs: string[] = ["Select Type"];
  if (selectedPrimary === "institution") {
    breadcrumbs.push("Institution Based");
    if (selectedInstitution === "college") breadcrumbs.push("College Based");
    if (selectedInstitution === "individual") breadcrumbs.push("Individual");
  }

  // ─── Tier detection ──
  const showInstitutionSub = false;
  const showCollegeForm = false;
  const showIndividualChips = false;
  const showPrimary = true;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16 relative">
      {/* Page container */}
      <div className="w-full max-w-5xl mx-auto">
        {/* ── Header ── */}
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-primary via-accent to-secondary mb-4">
            Select Interview Type
          </h1>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Choose how you&apos;d like to prepare. We&apos;ll tailor the
            experience to match your goals.
          </p>
        </motion.div>

        {/* ── Breadcrumb ── */}
        {breadcrumbs.length > 1 && (
          <motion.div
            className="flex items-center gap-2 mb-8 text-sm"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <button
              onClick={handleBack}
              className="flex items-center gap-1 text-primary hover:text-primary/80 transition-colors font-medium"
            >
              <ChevronLeft className="w-4 h-4" />
              Back
            </button>
            <span className="text-muted-foreground/40">|</span>
            {breadcrumbs.map((crumb, i) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && (
                  <ChevronRight className="w-3 h-3 text-muted-foreground/40" />
                )}
                <span
                  className={
                    i === breadcrumbs.length - 1
                      ? "text-foreground font-medium"
                      : "text-muted-foreground"
                  }
                >
                  {crumb}
                </span>
              </span>
            ))}
          </motion.div>
        )}

        {/* ── Cards area ── */}
        <AnimatePresence mode="wait">
          {/* ════ TIER 1 — Primary cards ════ */}
          {showPrimary && (
            <motion.div
              key="primary"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10"
            >
              {PRIMARY_TYPES.map((type) => {
                const isSelected = selectedPrimary === type.id;
                const Icon = type.icon;
                return (
                  <motion.div
                    key={type.id}
                    variants={cardVariants}
                    whileHover={{ y: -6, scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setSelectedPrimary(type.id)}
                    className={`
                      relative group cursor-pointer rounded-2xl p-8
                      bg-card border-2 transition-all duration-300
                      ${isSelected
                        ? `${type.borderColor} shadow-xl ${type.glowColor}`
                        : "border-border hover:border-primary/20 shadow-md hover:shadow-lg"
                      }
                    `}
                  >
                    {/* Selected badge */}
                    <AnimatePresence>
                      {isSelected && (
                        <motion.div
                          initial={{ scale: 0, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          exit={{ scale: 0, opacity: 0 }}
                          className="absolute top-4 right-4 w-7 h-7 rounded-full bg-primary flex items-center justify-center"
                        >
                          <Check className="w-4 h-4 text-primary-foreground" />
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Icon */}
                    <div
                      className={`
                        w-16 h-16 rounded-2xl flex items-center justify-center mb-6
                        bg-gradient-to-br ${type.gradient}
                        group-hover:scale-110 transition-transform duration-300
                      `}
                    >
                      <Icon className={`w-8 h-8 ${type.accentColor}`} />
                    </div>

                    {/* Text */}
                    <h3 className="text-xl font-bold text-foreground mb-2">
                      {type.title}
                    </h3>
                    <p className="text-muted-foreground text-sm leading-relaxed">
                      {type.description}
                    </p>

                    {/* Bottom accent line */}
                    <div
                      className={`
                        absolute bottom-0 left-6 right-6 h-1 rounded-full
                        transition-all duration-300
                        ${isSelected
                          ? `bg-gradient-to-r ${type.gradient} opacity-100`
                          : "bg-border opacity-0 group-hover:opacity-50"
                        }
                      `}
                    />
                  </motion.div>
                );
              })}
            </motion.div>
          )}

          {/* ════ TIER 2 — Institution sub-selection ════ */}
          {showInstitutionSub && (
            <motion.div
              key="institution-sub"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto mb-10"
            >
              {INSTITUTION_SUB_TYPES.map((type) => {
                const Icon = type.icon;
                return (
                  <motion.div
                    key={type.id}
                    variants={cardVariants}
                    whileHover={{ y: -6, scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setSelectedInstitution(type.id)}
                    className={`
                      relative group cursor-pointer rounded-2xl p-8
                      bg-card border-2 border-border
                      hover:${type.borderColor} shadow-md hover:shadow-xl
                      transition-all duration-300
                    `}
                  >
                    <div
                      className={`
                        w-16 h-16 rounded-2xl flex items-center justify-center mb-6
                        bg-gradient-to-br ${type.gradient}
                        group-hover:scale-110 transition-transform duration-300
                      `}
                    >
                      <Icon className={`w-8 h-8 ${type.accentColor}`} />
                    </div>

                    <h3 className="text-xl font-bold text-foreground mb-2">
                      {type.title}
                    </h3>
                    <p className="text-muted-foreground text-sm leading-relaxed">
                      {type.description}
                    </p>

                    {/* Hover arrow */}
                    <div className="absolute top-8 right-8 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                      <ArrowRight
                        className={`w-5 h-5 ${type.accentColor}`}
                      />
                    </div>
                  </motion.div>
                );
              })}
            </motion.div>
          )}

          {/* ════ TIER 3a — College form ════ */}
          {showCollegeForm && (
            <motion.div
              key="college-form"
              variants={panelVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="max-w-2xl mx-auto mb-10"
            >
              <div className="bg-card border border-border rounded-2xl p-8 shadow-lg relative overflow-hidden">
                {/* Subtle campus accent */}
                <div className="absolute top-0 right-0 w-32 h-32 opacity-[0.04] pointer-events-none">
                  <GraduationCap className="w-full h-full text-primary" />
                </div>

                {/* Header */}
                <div className="flex items-center gap-3 mb-8">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                    <School className="w-5 h-5 text-emerald-500" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-foreground">
                      College Details
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Select your institution and domain
                    </p>
                  </div>
                </div>

                {/* College dropdown */}
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-semibold text-foreground mb-2">
                      College Name
                    </label>
                    <div className="relative">
                      <div
                        onClick={() =>
                          setIsCollegeDropdownOpen(!isCollegeDropdownOpen)
                        }
                        className={`
                          w-full px-4 py-3 rounded-xl border-2 cursor-pointer
                          flex items-center justify-between
                          bg-background transition-all duration-200
                          ${isCollegeDropdownOpen
                            ? "border-primary shadow-md"
                            : "border-border hover:border-primary/30"
                          }
                        `}
                      >
                        <span
                          className={
                            selectedCollege
                              ? "text-foreground"
                              : "text-muted-foreground"
                          }
                        >
                          {selectedCollege || "Select your college..."}
                        </span>
                        <ChevronRight
                          className={`w-4 h-4 text-muted-foreground transition-transform duration-200 ${isCollegeDropdownOpen ? "rotate-90" : ""
                            }`}
                        />
                      </div>

                      <AnimatePresence>
                        {isCollegeDropdownOpen && (
                          <motion.div
                            initial={{ opacity: 0, y: -8, scaleY: 0.95 }}
                            animate={{ opacity: 1, y: 0, scaleY: 1 }}
                            exit={{ opacity: 0, y: -8, scaleY: 0.95 }}
                            transition={{ duration: 0.15 }}
                            className="absolute z-50 top-full left-0 right-0 mt-2 bg-card border border-border rounded-xl shadow-xl overflow-hidden origin-top"
                          >
                            {/* Search */}
                            <div className="p-3 border-b border-border">
                              <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <input
                                  type="text"
                                  value={collegeSearch}
                                  onChange={(e) =>
                                    setCollegeSearch(e.target.value)
                                  }
                                  placeholder="Search colleges..."
                                  className="w-full pl-9 pr-4 py-2 rounded-lg bg-background border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-colors"
                                  autoFocus
                                />
                              </div>
                            </div>

                            {/* Options */}
                            <div className="max-h-48 overflow-y-auto">
                              {filteredColleges.length > 0 ? (
                                filteredColleges.map((college) => (
                                  <button
                                    key={college}
                                    onClick={() => {
                                      setSelectedCollege(college);
                                      setIsCollegeDropdownOpen(false);
                                      setCollegeSearch("");
                                    }}
                                    className={`
                                      w-full text-left px-4 py-2.5 text-sm
                                      transition-colors duration-150
                                      ${selectedCollege === college
                                        ? "bg-primary/10 text-primary font-medium"
                                        : "text-foreground hover:bg-accent/10"
                                      }
                                    `}
                                  >
                                    <span className="flex items-center gap-2">
                                      <GraduationCap className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                                      {college}
                                    </span>
                                  </button>
                                ))
                              ) : (
                                <div className="px-4 py-6 text-center text-sm text-muted-foreground">
                                  No colleges found
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>

                  {/* Domain dropdown */}
                  <div>
                    <label className="block text-sm font-semibold text-foreground mb-2">
                      College Domain / School
                    </label>
                    <select
                      value={selectedDomain || ""}
                      onChange={(e) =>
                        setSelectedDomain(e.target.value || null)
                      }
                      className={`
                        w-full px-4 py-3 rounded-xl border-2 bg-background
                        text-sm transition-all duration-200 appearance-none
                        cursor-pointer
                        ${selectedDomain
                          ? "border-primary/30 text-foreground"
                          : "border-border text-muted-foreground"
                        }
                        hover:border-primary/30 focus:border-primary focus:outline-none
                      `}
                    >
                      <option value="">Select domain...</option>
                      {COLLEGE_DOMAINS.map((domain) => (
                        <option key={domain} value={domain}>
                          {domain}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Selected summary */}
                {selectedCollege && selectedDomain && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="mt-6 p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20"
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <Check className="w-4 h-4 text-emerald-500" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {selectedCollege}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {selectedDomain}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>
            </motion.div>
          )}

          {/* ════ TIER 3b — Individual interview chips ════ */}
          {showIndividualChips && (
            <motion.div
              key="individual-chips"
              variants={panelVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="max-w-3xl mx-auto mb-10"
            >
              <div className="bg-card border border-border rounded-2xl p-8 shadow-lg">
                {/* Header */}
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
                    <User className="w-5 h-5 text-violet-500" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-foreground">
                      Interview Categories
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Select one or more categories
                    </p>
                  </div>
                </div>

                <p className="text-sm text-muted-foreground mb-6 ml-[52px]">
                  Choose the interview types you want to practice. You can
                  select multiple.
                </p>

                {/* Chips grid */}
                <div className="flex flex-wrap gap-3 ml-[52px]">
                  {INTERVIEW_CHIPS.map((chip, i) => {
                    const isActive = selectedChips.has(chip.id);
                    return (
                      <motion.button
                        key={chip.id}
                        custom={i}
                        variants={chipVariants}
                        initial="hidden"
                        animate="visible"
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => toggleChip(chip.id)}
                        className={`
                          inline-flex items-center gap-2 px-5 py-2.5 rounded-full
                          text-sm font-medium
                          border-2 transition-all duration-200
                          ${isActive
                            ? "bg-primary/10 border-primary text-primary shadow-md shadow-primary/10"
                            : "bg-card border-border text-foreground hover:border-primary/30 hover:bg-accent/5"
                          }
                        `}
                      >
                        <span className="text-base">{chip.emoji}</span>
                        <span>{chip.label}</span>
                        <AnimatePresence>
                          {isActive && (
                            <motion.span
                              initial={{ scale: 0, width: 0 }}
                              animate={{ scale: 1, width: "auto" }}
                              exit={{ scale: 0, width: 0 }}
                              transition={{ type: "spring", stiffness: 500, damping: 25 }}
                            >
                              <Check className="w-3.5 h-3.5" />
                            </motion.span>
                          )}
                        </AnimatePresence>
                      </motion.button>
                    );
                  })}
                </div>

                {/* Selection count */}
                {selectedChips.size > 0 && (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-xs text-primary font-medium mt-4 ml-[52px]"
                  >
                    {selectedChips.size} categor{selectedChips.size === 1 ? "y" : "ies"}{" "}
                    selected
                  </motion.p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Start button ── */}
        <motion.div
          className="flex justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          <button
            onClick={handleStart}
            disabled={!canStart}
            className={`
              group inline-flex items-center gap-3 px-10 py-4 rounded-2xl
              text-lg font-bold transition-all duration-300
              ${canStart
                ? "bg-gradient-to-r from-primary to-accent text-primary-foreground shadow-lg shadow-primary/25 hover:shadow-xl hover:shadow-primary/35 hover:scale-105"
                : "bg-muted text-muted-foreground cursor-not-allowed"
              }
            `}
          >
            Start Interview
            <ArrowRight
              className={`w-5 h-5 transition-transform duration-300 ${canStart ? "group-hover:translate-x-1" : ""
                }`}
            />
          </button>
        </motion.div>
      </div>
    </div>
  );
}
