import { useParams } from 'react-router-dom';
import { Placeholder } from '../../components/ui';

export default function PollPage() {
  const { pollId } = useParams();
  return <Placeholder title="Encuesta" description="Aquí podrás consultar una encuesta y votar por una opción." detail={`Identificador: ${pollId}`} />;
}
