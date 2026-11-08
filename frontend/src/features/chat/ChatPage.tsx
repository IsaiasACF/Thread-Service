import { useParams } from 'react-router-dom';
import { Placeholder } from '../../components/ui';

export default function ChatPage() {
  const { channelId } = useParams();
  return <Placeholder title="Chat y respuestas" description="Aquí podrás consultar mensajes y participar en sus conversaciones." detail={`Identificador: ${channelId}`} />;
}
