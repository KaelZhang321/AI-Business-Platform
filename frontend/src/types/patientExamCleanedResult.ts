export interface PatientExamCleanedResultResponse {
  code: number;
  message: string;
  data: PatientExamCleanedResultData;
}

export interface PatientExamCleanedResultData {
  study_id: string;
  patient_name: string;
  gender: string;
  exam_time: string;
  package_name: string;
  summary: {
    categories: string[];
    total_indicators: number;
    abnormal_count: number;
  };
  indicators: PatientExamIndicator[];
}

export interface PatientExamIndicator {
  category: string | null;
  value: string | null;
  unit: string;
  standard_code: string;
  standard_name: string;
  reference_range: string | null;
  ref_min: string | number | null;
  ref_max: string | number | null;
  is_abnormal: boolean;
  abnormal_direction: 'high' | 'low' | null;
}
