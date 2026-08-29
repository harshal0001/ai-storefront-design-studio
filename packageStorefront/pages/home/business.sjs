const backLabelTypeClass = (type = 'keyword') => {
  switch (type) {
    case 'keyword': return 'store-label';
    case 'popularFeature': return 'store-label store-label-primary';
    case 'averagePrice': return 'store-label-category';
    default: return 'store-label';
  }
};

const abbreviationOfWeek = {
  MONDAY: 'Mon',
  TUESDAY: 'Tus',
  WEDNESDAY: 'Wed',
  THURSDAY: 'Thu',
  FRIDAY: 'Fri',
  SATURDAY: 'Sat',
  SUNDAY: 'Sun',
}
const backAbbreviationOfWeek = (week) => abbreviationOfWeek[week] || ''

export default {
  backLabelTypeClass,
  backAbbreviationOfWeek,
};
