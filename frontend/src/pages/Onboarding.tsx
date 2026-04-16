import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, ChevronLeft, Check, Building2 } from "lucide-react";
import { cn } from "../lib/utils";
import { api } from "../lib/api";

interface Step {
  key: string;
  label: string;
  placeholder: string;
  defaultValue: string;
  multiline?: boolean;
}

const STEPS: Step[] = [
  {
    key: "center_name",
    label: "What's the name of your center?",
    placeholder: "e.g., Sunrise Early Learning",
    defaultValue: "Sunrise Early Learning",
  },
  {
    key: "operator_email",
    label: "What's your email? (for escalations)",
    placeholder: "e.g., maria@sunrise-daycare.example",
    defaultValue: "maria@sunrise-daycare.example",
  },
  {
    key: "operating_hours",
    label: "What are your operating hours?",
    placeholder: "e.g., Monday through Friday, 6:30 AM to 6:00 PM",
    defaultValue:
      "Monday through Friday, 6:30 AM to 6:00 PM. Drop-off window: 6:30–9:00 AM. Pick-up deadline: 6:00 PM. Late fee of $1/minute after 6:05 PM.",
    multiline: true,
  },
  {
    key: "holidays_closed",
    label: "What holidays are you closed?",
    placeholder: "List the holidays your center observes...",
    defaultValue:
      "New Year's Day, Martin Luther King Jr. Day, Presidents' Day, Memorial Day, Independence Day, Labor Day, Veterans Day, Thanksgiving Day, Day After Thanksgiving, Christmas Eve, Christmas Day. If a holiday falls on a weekend, we observe it on the nearest weekday.",
    multiline: true,
  },
  {
    key: "tuition_infant",
    label: "What is your monthly tuition for infants?",
    placeholder: "e.g., $1,800/month",
    defaultValue: "$1,800/month",
  },
  {
    key: "tuition_toddler",
    label: "What is your monthly tuition for toddlers?",
    placeholder: "e.g., $1,550/month",
    defaultValue: "$1,550/month",
  },
  {
    key: "tuition_preschool",
    label: "What is your monthly tuition for preschool?",
    placeholder: "e.g., $1,300/month",
    defaultValue: "$1,300/month",
  },
  {
    key: "sick_policy",
    label: "What's your policy on sick children?",
    placeholder: "Describe your fever threshold, return criteria, etc.",
    defaultValue:
      "Children must stay home with a fever of 100.4°F or higher, vomiting, or diarrhea within 24 hours. Children may return when symptom-free for 24 hours without fever-reducing medication. A doctor's note is required for contagious illnesses.",
    multiline: true,
  },
  {
    key: "meals_info",
    label: "Do you provide meals? What should parents know?",
    placeholder: "Describe your meal program, allergy policies, etc.",
    defaultValue:
      "We provide breakfast, lunch, and two snacks daily, included in tuition. We are a peanut-free facility. All allergies must be documented. Parents may send food from home (labeled, no peanut products). Weekly menus posted in Brightwheel every Friday.",
    multiline: true,
  },
  {
    key: "tour_scheduling",
    label: "How do parents schedule a tour?",
    placeholder: "Describe tour availability and scheduling process...",
    defaultValue:
      "Tours are available Monday–Friday, 9:30–11:00 AM and 3:30–5:00 PM. Each tour lasts about 30 minutes. Parents can schedule by phone (503-555-0147), email (maria@sunrise-daycare.example), or through our AI chat. Children are welcome to attend.",
    multiline: true,
  },
];

export function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(STEPS.map((s) => [s.key, s.defaultValue]))
  );
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const currentStep = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const progress = ((step + 1) / STEPS.length) * 100;

  const handleNext = async () => {
    if (isLast) {
      setSubmitting(true);
      try {
        await api.completeOnboarding({
          center_name: values.center_name,
          operator_email: values.operator_email,
          operating_hours: values.operating_hours,
          holidays_closed: values.holidays_closed,
          tuition_infant: values.tuition_infant,
          tuition_toddler: values.tuition_toddler,
          tuition_preschool: values.tuition_preschool,
          sick_policy: values.sick_policy,
          meals_info: values.meals_info,
          tour_scheduling: values.tour_scheduling,
        });
        setDone(true);
      } catch (err) {
        console.error(err);
      } finally {
        setSubmitting(false);
      }
    } else {
      setStep(step + 1);
    }
  };

  if (done) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-background p-4">
        <div className="max-w-md w-full text-center space-y-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 mx-auto">
            <Check className="h-8 w-8 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Your AI Front Desk is ready!</h1>
          <p className="text-muted-foreground">
            {values.center_name} is all set up. Parents can now chat with your AI assistant,
            and you can manage everything from the operator dashboard.
          </p>
          <div className="flex flex-col gap-3">
            <button
              onClick={() => navigate("/")}
              className="rounded-xl bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Open Parent Chat
            </button>
            <button
              onClick={() => navigate("/operator")}
              className="rounded-xl border border-border px-6 py-3 text-sm font-medium text-foreground hover:bg-secondary transition-colors"
            >
              Open Operator Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border px-4 py-3">
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <Building2 className="h-5 w-5 text-primary" />
          <div>
            <h1 className="text-sm font-semibold text-foreground">Set Up Your AI Front Desk</h1>
            <p className="text-xs text-muted-foreground">Step {step + 1} of {STEPS.length}</p>
          </div>
        </div>
      </header>

      {/* Progress bar */}
      <div className="h-1 bg-secondary">
        <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="max-w-lg w-full space-y-6">
          <label className="block text-lg font-medium text-foreground">
            {currentStep.label}
          </label>

          {currentStep.multiline ? (
            <textarea
              value={values[currentStep.key]}
              onChange={(e) => setValues({ ...values, [currentStep.key]: e.target.value })}
              placeholder={currentStep.placeholder}
              className="w-full rounded-xl border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring min-h-[120px] resize-y"
              autoFocus
            />
          ) : (
            <input
              type={currentStep.key === "operator_email" ? "email" : "text"}
              value={values[currentStep.key]}
              onChange={(e) => setValues({ ...values, [currentStep.key]: e.target.value })}
              placeholder={currentStep.placeholder}
              className="w-full rounded-xl border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
            />
          )}

          <div className="flex justify-between">
            <button
              onClick={() => setStep(step - 1)}
              disabled={step === 0}
              className={cn(
                "flex items-center gap-1 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors",
                step === 0
                  ? "text-muted-foreground opacity-50"
                  : "text-foreground hover:bg-secondary"
              )}
            >
              <ChevronLeft className="h-4 w-4" /> Back
            </button>
            <button
              onClick={handleNext}
              disabled={submitting || !values[currentStep.key]?.trim()}
              className="flex items-center gap-1 rounded-xl bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {submitting ? "Saving..." : isLast ? "Finish Setup" : "Next"}
              {!isLast && <ChevronRight className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
