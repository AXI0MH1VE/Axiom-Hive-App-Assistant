interface Props {
  confidence: 'High' | 'Medium' | 'Low';
}

const styles = {
  High: 'bg-green-100 text-green-800 border-green-200',
  Medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  Low: 'bg-red-100 text-red-800 border-red-200',
};

export function ConfidenceBadge({ confidence }: Props) {
  const style = styles[confidence] || styles.Low;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${style}`}
      title={`Confidence: ${confidence}`}
    >
      {confidence}
    </span>
  );
}
