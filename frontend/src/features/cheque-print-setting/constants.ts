export const YES_NO = ["Y", "N"] as const;
export const PRINTER_MODES = ["P", "L"] as const;

export type ChequePrintFormState = {
  cheque_setting_id: string;
  bank_name: string;
  width_of_chq: string;
  height_of_chq: string;
  printer_mode: string;
  date_from_top: string;
  date_from_left: string;
  name_from_top: string;
  name_from_left: string;
  name_char_count: string;
  amt_word_line1_from_top: string;
  amt_word_line1_from_left: string;
  amt_word_line1_char_count: string;
  amt_word_line2_from_top: string;
  amt_word_line2_from_left: string;
  amt_word_line2_char_count: string;
  amt_figure_from_top: string;
  amt_figure_from_left: string;
  company_name_required: string;
  comp_name_from_top: string;
  comp_name_from_left: string;
  comp_name_char_count: string;
  tds_print_required: string;
  tds_from_top: string;
  tds_from_left: string;
  tds_char_count: string;
  sign1_required: string;
  print_in_sign1: string;
  sign1_from_top: string;
  sign1_from_left: string;
  sign2_required: string;
  print_in_sign2: string;
  sign2_from_top: string;
  sign2_from_left: string;
  sign3_required: string;
  print_in_sign3: string;
  sign3_from_top: string;
  sign3_from_left: string;
  date_font: string;
  name_font: string;
  amt_word_line1_font: string;
  amt_figure_font: string;
  tds_figure_font: string;
  amt_word_line2_font: string;
  show_star: string;
};

export function emptyChequePrintForm(): ChequePrintFormState {
  return {
    cheque_setting_id: "",
    bank_name: "",
    width_of_chq: "",
    height_of_chq: "",
    printer_mode: "P",
    date_from_top: "",
    date_from_left: "",
    name_from_top: "",
    name_from_left: "",
    name_char_count: "",
    amt_word_line1_from_top: "",
    amt_word_line1_from_left: "",
    amt_word_line1_char_count: "",
    amt_word_line2_from_top: "",
    amt_word_line2_from_left: "",
    amt_word_line2_char_count: "",
    amt_figure_from_top: "",
    amt_figure_from_left: "",
    company_name_required: "N",
    comp_name_from_top: "",
    comp_name_from_left: "",
    comp_name_char_count: "",
    tds_print_required: "N",
    tds_from_top: "",
    tds_from_left: "",
    tds_char_count: "",
    sign1_required: "N",
    print_in_sign1: "",
    sign1_from_top: "",
    sign1_from_left: "",
    sign2_required: "N",
    print_in_sign2: "",
    sign2_from_top: "",
    sign2_from_left: "",
    sign3_required: "N",
    print_in_sign3: "",
    sign3_from_top: "",
    sign3_from_left: "",
    date_font: "10",
    name_font: "10",
    amt_word_line1_font: "10",
    amt_figure_font: "10",
    tds_figure_font: "10",
    amt_word_line2_font: "10",
    show_star: "N",
  };
}

export function chequePrintFormFromRecord(
  row: Record<string, unknown>,
): ChequePrintFormState {
  const base = emptyChequePrintForm();
  const next = { ...base };
  for (const key of Object.keys(base) as (keyof ChequePrintFormState)[]) {
    if (row[key] !== undefined && row[key] !== null) {
      next[key] = String(row[key]);
    }
  }
  return next;
}

export function chequePrintFormToPayload(
  form: ChequePrintFormState,
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...form };
  if (!form.cheque_setting_id) {
    delete payload.cheque_setting_id;
  }
  return payload;
}
