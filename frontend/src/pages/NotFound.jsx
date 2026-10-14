import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button, EmptyState } from '../components/ui'

export default function NotFound() {
  return <EmptyState icon={Compass} title="Page not found" description="That page does not exist." action={<Link to="/"><Button variant="primary">Back to overview</Button></Link>} />
}
