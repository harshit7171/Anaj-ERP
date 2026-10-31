function MandatoryLabel({ label, required = false }: { label: string; required?: boolean }) {
  return (
    <span className="mandi-label">
      {label}
      {required && <span aria-hidden className="mandi-required">*</span>}
    </span>
  );
}

export default MandatoryLabel;
