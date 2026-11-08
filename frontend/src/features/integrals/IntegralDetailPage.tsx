import { useParams } from 'react-router-dom';
import { Placeholder } from '../../components/ui';

export default function IntegralDetailPage() {
  const { id } = useParams();
  return <Placeholder title="Detalle de integral" description="Aquí podrás revisar el resultado y estado de un cálculo." detail={`Identificador: ${id}`} />;
}
